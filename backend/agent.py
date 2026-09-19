import os
import json
import logging

logger = logging.getLogger("agent")

FALLBACK_DIAGNOSES = {
    "LOCK_CONTENTION": {
        "model": "dbpulse rule-based runbook",
        "root_cause": "PostgreSQL reports one or more sessions waiting on locks held by other backends. Inspect the current blocking chain before choosing whether to cancel a query or resolve the owning transaction.",
        "citations": "source: pg_stat_activity, pg_locks",
        "remediation_steps": [
            {
                "step": 1,
                "title": "Inspect blocking query details and duration",
                "sql": "SELECT pid, pg_blocking_pids(pid) AS blocked_by, now() - query_start AS duration, query, state\nFROM pg_stat_activity\nWHERE cardinality(pg_blocking_pids(pid)) > 0;"
            },
            {
                "step": 2,
                "title": "Review the blocker before remediation",
                "sql": "SELECT DISTINCT blocker.pid, blocker.usename, blocker.state, blocker.query\nFROM pg_stat_activity waiting\nCROSS JOIN LATERAL unnest(pg_blocking_pids(waiting.pid)) AS blocker_pid\nJOIN pg_stat_activity blocker ON blocker.pid = blocker_pid;"
            }
        ],
        "disclaimer": "generates SQL for a human to run — nothing executes automatically."
    },
    "POOL_EXHAUSTION": {
        "model": "dbpulse rule-based runbook",
        "root_cause": "Observed connections have crossed the configured capacity threshold. Inspect connection state and client ownership to distinguish active demand from stale or idle-in-transaction sessions.",
        "citations": "source: pg_stat_activity, pg_stat_database",
        "remediation_steps": [
            {
                "step": 1,
                "title": "List all idle-in-transaction sessions",
                "sql": "SELECT pid, usename, client_addr, now() - state_change AS idle_duration \nFROM pg_stat_activity \nWHERE state = 'idle in transaction' \nORDER BY idle_duration DESC;"
            },
            {
                "step": 2,
                "title": "Terminate stale idle connections (> 5 mins)",
                "sql": "SELECT pg_terminate_backend(pid) \nFROM pg_stat_activity \nWHERE state = 'idle in transaction' \n  AND now() - state_change > interval '5 minutes';"
            }
        ],
        "disclaimer": "generates SQL for a human to run — nothing executes automatically."
    },
    "RUNAWAY_QUERY": {
        "model": "dbpulse rule-based runbook",
        "root_cause": "PostgreSQL reports an active query beyond the configured runtime threshold. Inspect its execution plan, wait event, and workload owner before cancellation or index changes.",
        "citations": "source: pg_stat_activity, DataFileRead wait events",
        "remediation_steps": [
            {
                "step": 1,
                "title": "Inspect longest-running active queries",
                "sql": "SELECT pid, now() - query_start AS runtime, wait_event_type, wait_event, query\nFROM pg_stat_activity\nWHERE state = 'active' AND pid <> pg_backend_pid()\nORDER BY query_start;"
            },
            {
                "step": 2,
                "title": "Capture the plan before changing schema",
                "sql": "-- Run EXPLAIN (ANALYZE, BUFFERS) only after reviewing the selected read query and its production impact."
            }
        ],
        "disclaimer": "generates SQL for a human to run — nothing executes automatically."
    }
}

class AgentEngine:
    def __init__(self, rag_engine):
        self.rag_engine = rag_engine
        self.provider = os.getenv("AGENT_PROVIDER", "deterministic").lower()
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.azure_foundry_endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_foundry_key = os.getenv("AZURE_FOUNDRY_KEY") or os.getenv("AZURE_OPENAI_KEY")
        self.azure_foundry_model = os.getenv("AZURE_FOUNDRY_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.azure_use_managed_identity = os.getenv("AZURE_FOUNDRY_USE_MANAGED_IDENTITY", "").lower() in {"1", "true", "yes"}
        self.last_provider_error = None

    def get_status(self):
        if self.provider == "deterministic":
            return {
                "provider": "deterministic rules",
                "configured": True,
                "model": "dbpulse rule-based runbook",
                "authentication": "none",
                "missing": [],
                "last_error": self.last_provider_error,
            }
        if self.azure_foundry_endpoint:
            missing = []
            if not self.azure_foundry_key and not self.azure_use_managed_identity:
                missing.append("authentication")
            if not self.azure_foundry_model:
                missing.append("model")
            return {
                "provider": "Azure AI Foundry",
                "configured": not missing,
                "model": self.azure_foundry_model,
                "authentication": "managed_identity" if self.azure_use_managed_identity else "api_key",
                "missing": missing,
                "last_error": self.last_provider_error,
            }
        if self.anthropic_key:
            return {"provider": "Anthropic", "configured": True, "model": "claude-3-5-sonnet-20241022", "missing": []}
        if self.openai_key:
            return {"provider": "OpenAI", "configured": True, "model": "gpt-4o", "missing": []}
        return {"provider": "deterministic fallback", "configured": False, "model": None, "missing": ["provider"]}

    @staticmethod
    def _parse_json_content(content):
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Model response did not contain a JSON object")
        return json.loads(content[start:end + 1])

    @staticmethod
    def _responses_api_text(response_body):
        for output in response_body.get("output", []):
            for content in output.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return content["text"]
        raise ValueError("Azure Responses API returned no output text")

    @staticmethod
    def _azure_http_error(api_name, response):
        summary = f"{api_name} returned HTTP {response.status_code}"
        try:
            error = response.json().get("error", {})
            code = error.get("code")
            message = error.get("message")
            details = ": ".join(str(value) for value in (code, message) if value)
            if details:
                return RuntimeError(f"{summary}: {details[:500]}")
        except (TypeError, ValueError, AttributeError):
            pass
        return RuntimeError(summary)

    @staticmethod
    def _azure_sdk_error(error):
        status_code = getattr(error, "status_code", None)
        summary = "Azure OpenAI SDK request failed"
        if status_code:
            summary = f"Azure OpenAI SDK returned HTTP {status_code}"
        body = getattr(error, "body", None)
        if not isinstance(body, dict):
            try:
                body = error.response.json()
            except (AttributeError, TypeError, ValueError):
                body = None
        if isinstance(body, dict):
            detail = body.get("error", body)
            if isinstance(detail, dict):
                values = (detail.get("code"), detail.get("message"), detail.get("param"))
                details = ": ".join(str(value) for value in values if value)
                if details:
                    return RuntimeError(f"{summary}: {details[:500]}")
        return RuntimeError(summary)

    def _call_azure_sdk(self, prompt):
        from openai import OpenAI

        base_url = self.azure_foundry_endpoint.rstrip("/")
        if base_url.endswith("/responses"):
            base_url = base_url[:-len("/responses")]
        client = OpenAI(base_url=base_url, api_key=self.azure_foundry_key)
        try:
            response = client.responses.create(model=self.azure_foundry_model, input=prompt)
        except Exception as error:
            raise self._azure_sdk_error(error) from error
        if not response.output_text:
            raise ValueError("Azure OpenAI SDK returned no output text")
        return response.output_text

    def _call_azure(self, requests_module, prompt):
        endpoint = self.azure_foundry_endpoint.rstrip("/")
        if endpoint.endswith("/responses") and not self.azure_use_managed_identity:
            return self._call_azure_sdk(prompt)

        headers = {"content-type": "application/json"}
        if self.azure_use_managed_identity:
            token_response = requests_module.get(
                "http://169.254.169.254/metadata/identity/oauth2/token",
                params={
                    "api-version": "2018-02-01",
                    "resource": os.getenv("AZURE_FOUNDRY_TOKEN_RESOURCE", "https://cognitiveservices.azure.com/"),
                },
                headers={"Metadata": "true"},
                timeout=3,
            )
            if token_response.status_code != 200:
                raise RuntimeError(f"Managed identity token request returned HTTP {token_response.status_code}")
            headers["Authorization"] = f"Bearer {token_response.json()['access_token']}"
        else:
            headers["Authorization"] = f"Bearer {self.azure_foundry_key}"

        if endpoint.endswith("/responses"):
            payload = {"model": self.azure_foundry_model, "input": prompt}
            response = requests_module.post(endpoint, json=payload, headers=headers, timeout=20)
            if response.status_code == 400:
                chat_endpoint = f"{endpoint[:-len('responses')]}chat/completions"
                chat_payload = {
                    "model": self.azure_foundry_model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                chat_response = requests_module.post(
                    chat_endpoint, json=chat_payload, headers=headers, timeout=20
                )
                if chat_response.status_code != 200:
                    raise self._azure_http_error("Azure Chat Completions API", chat_response)
                return chat_response.json()["choices"][0]["message"]["content"]
            if response.status_code != 200:
                raise self._azure_http_error("Azure Responses API", response)
            return self._responses_api_text(response.json())

        if "/chat/completions" not in endpoint:
            endpoint = (
                f"{endpoint}/openai/deployments/{self.azure_foundry_model}/chat/completions"
                f"?api-version={os.getenv('AZURE_OPENAI_API_VERSION', '2024-10-21')}"
            )
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        response = requests_module.post(endpoint, json=payload, headers=headers, timeout=20)
        if response.status_code != 200:
            raise self._azure_http_error("Azure Chat Completions API", response)
        return response.json()["choices"][0]["message"]["content"]

    def diagnose_anomaly(self, anomaly_info, metrics_info):
        if not anomaly_info:
            return {
                "model": "dbpulse Agent",
                "root_cause": "All PostgreSQL database targets are operating normally within safety thresholds.",
                "citations": "source: pg_stat_activity",
                "remediation_steps": [],
                "disclaimer": "generates SQL for a human to run — nothing executes automatically."
            }

        anomaly_type = anomaly_info.get("type", "LOCK_CONTENTION")
        
        # Retrieve RAG context
        query = f"{anomaly_type} {anomaly_info.get('title', '')} {anomaly_info.get('target_table', '')}"
        relevant_docs = self.rag_engine.retrieve_relevant_docs(query)
        prompt = (
            f"Analyze this PostgreSQL anomaly: {json.dumps(anomaly_info)}. "
            f"Current fleet metrics: {json.dumps(metrics_info)}. "
            f"RAG context: {json.dumps([d['content'] for d in relevant_docs])}. "
            "Return a valid JSON object with keys: root_cause (string), citations (string), "
            "remediation_steps (list of objects with step, title, sql)."
        )
        
        # Attempt LLM API call if key configured
        if self.provider != "deterministic" and (self.anthropic_key or self.openai_key or self.get_status()["configured"]):
            try:
                import requests
                # 1. Azure AI Foundry / Azure OpenAI Endpoint
                if self.get_status()["configured"] and self.azure_foundry_endpoint:
                    content = self._call_azure(requests, prompt)
                    res_json = self._parse_json_content(content)
                    self.last_provider_error = None
                    res_json["model"] = f"Azure AI Foundry: {self.azure_foundry_model} (Live LLM + RAG)"
                    res_json["disclaimer"] = "generates SQL for a human to run — nothing executes automatically."
                    return res_json

                # 2. Anthropic API
                elif self.anthropic_key:
                    headers = {
                        "x-api-key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }
                    payload = {
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 800,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    resp = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=20)
                    if resp.status_code == 200:
                        content = resp.json()["content"][0]["text"]
                        res_json = self._parse_json_content(content)
                        res_json["model"] = "Claude 3.5 Sonnet (Live LLM + RAG)"
                        res_json["disclaimer"] = "generates SQL for a human to run — nothing executes automatically."
                        return res_json

                # 3. OpenAI API
                elif self.openai_key:
                    headers = {
                        "Authorization": f"Bearer {self.openai_key}",
                        "content-type": "application/json"
                    }
                    payload = {
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    resp = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=20)
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        res_json = self._parse_json_content(content)
                        res_json["model"] = "GPT-4o (Live LLM + RAG)"
                        res_json["disclaimer"] = "generates SQL for a human to run — nothing executes automatically."
                        return res_json

            except RuntimeError as error:
                self.last_provider_error = str(error)
                logger.warning("Live LLM call failed: %s; using deterministic fallback", self.last_provider_error)
            except Exception as error:
                self.last_provider_error = f"Invalid provider response ({type(error).__name__})"
                logger.warning("Live LLM call failed (%s), using deterministic fallback", type(error).__name__)

        # Guaranteed high-quality fallback
        diagnosis = FALLBACK_DIAGNOSES.get(anomaly_type, FALLBACK_DIAGNOSES["LOCK_CONTENTION"]).copy()
        diagnosis["citations"] = diagnosis["citations"].replace("source:", "Runbook references:")
        return diagnosis
