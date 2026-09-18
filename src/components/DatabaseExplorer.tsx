import { useEffect, useState } from 'react';

interface TableInfo { schema: string; name: string; row_count: number }
interface Preview { columns: string[]; rows: Array<Array<string | null>> }

export function DatabaseExplorer({ database }: { database: string }) {
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [message, setMessage] = useState('Loading table inventory...');

  useEffect(() => {
    let cancelled = false;
    setTables([]); setSelectedTable(''); setPreview(null); setMessage('Loading table inventory...');
    fetch(`/api/databases/${encodeURIComponent(database)}/tables`)
      .then(async response => {
        if (!response.ok) throw new Error('Inventory unavailable');
        return response.json();
      })
      .then(data => {
        if (cancelled) return;
        setTables(data.tables);
        setMessage(data.tables.length ? 'Select a table to preview its first 20 rows.' : 'No public tables found. Seed this database first.');
      })
      .catch(() => { if (!cancelled) setMessage('Table inventory unavailable. Check database permissions and backend status.'); });
    return () => { cancelled = true; };
  }, [database]);

  const selectTable = async (table: string) => {
    setSelectedTable(table); setPreview(null); setMessage('Loading preview...');
    try {
      const response = await fetch(`/api/databases/${encodeURIComponent(database)}/tables/${encodeURIComponent(table)}/rows?limit=20`);
      if (!response.ok) throw new Error('Preview unavailable');
      const data = await response.json();
      setPreview({ columns: data.columns, rows: data.rows });
      setMessage('Read-only preview, limited to 20 rows.');
    } catch { setMessage('Preview unavailable.'); }
  };

  return <section className="database-explorer">
    <div className="explorer-header">
      <div><div className="section-label">Database Data</div><h2>{database}</h2></div>
      <span>{message}</span>
    </div>
    <div className="table-tabs" role="tablist">
      {tables.map(table => <button key={table.name} className={selectedTable === table.name ? 'active' : ''}
        onClick={() => selectTable(table.name)} role="tab" aria-selected={selectedTable === table.name}>
        {table.name}<small>{table.row_count.toLocaleString()} rows</small>
      </button>)}
    </div>
    {preview && <div className="data-table-wrap"><table className="data-table">
      <thead><tr>{preview.columns.map(column => <th key={column}>{column}</th>)}</tr></thead>
      <tbody>{preview.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((value, cellIndex) => <td key={cellIndex}>{value ?? 'NULL'}</td>)}</tr>)}</tbody>
    </table></div>}
  </section>;
}