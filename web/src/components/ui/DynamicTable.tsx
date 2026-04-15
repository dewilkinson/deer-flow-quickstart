"use client";

import React from 'react';
import { motion } from 'framer-motion';

export type DynamicTableHeader = string;

export type DynamicTableRow = (string | number | { type: string; value: any })[];

interface DynamicTableProps {
  headers: DynamicTableHeader[];
  rows: DynamicTableRow[];
  id?: string;
}

export const DynamicTable: React.FC<DynamicTableProps> = ({ headers, rows, id }) => {
  const renderCell = (cell: any, idx: number) => {
    if (typeof cell === 'object' && cell !== null && cell.type === 'indicator') {
      const value = Number(cell.value) || 0;
      return (
        <div className="flex items-center gap-1.5" key={`cell-${idx}`}>
          {[...Array(5)].map((_, i) => (
            <div 
              key={i}
              className={`w-2 h-2 rounded-full transform transition-all duration-300 ${
                i < value 
                  ? 'bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.6)]' 
                  : 'bg-slate-700/50'
              }`}
            />
          ))}
        </div>
      );
    }

    if (typeof cell === 'number') {
      return <span className="font-mono text-indigo-300" key={`cell-${idx}`}>{cell.toLocaleString()}</span>;
    }

    return <span className="text-slate-300" key={`cell-${idx}`}>{String(cell)}</span>;
  };

  return (
    <div id={id} className="w-full overflow-hidden border border-white/10 bg-black/20 backdrop-blur-md rounded-xl shadow-2xl">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-white/5 border-b border-white/10">
              {headers.map((header, i) => (
                <th key={i} className="px-4 py-3 font-black uppercase tracking-widest text-slate-500 whitespace-nowrap">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map((row, i) => (
              <motion.tr 
                key={i}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className="hover:bg-white/[0.02] transition-colors"
              >
                {row.map((cell, j) => (
                  <td key={j} className="px-4 py-3 whitespace-nowrap align-middle">
                    {renderCell(cell, j)}
                  </td>
                ))}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
