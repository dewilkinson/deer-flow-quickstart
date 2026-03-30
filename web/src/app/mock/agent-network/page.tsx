'use client';

import React, { useState, useCallback, useRef } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
} from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Predefined layout map for standard nodes
const layoutMap: Record<string, { x: number; y: number }> = {
  'agent-planner': { x: 250, y: 50 },
  'agent-researcher': { x: 50, y: 200 },
  'agent-writer': { x: 450, y: 200 },
  'storage-global': { x: 250, y: 400 },
  'storage-local': { x: 450, y: 400 },
  'storage-obsidian': { x: 50, y: 400 },
};

export default function NetworkVisualizer() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [logs, setLogs] = useState<{ id: number; text: string }[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const logCounter = useRef(0);

  const addLog = (text: string) => {
    logCounter.current += 1;
    setLogs((prev) => [...prev, { id: logCounter.current, text }]);
  };

  const startSimulation = useCallback(() => {
    setIsSimulating(true);
    setNodes([]);
    setEdges([]);
    setLogs([]);

    const eventSource = new EventSource('http://localhost:8001/api/simulate');

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'init') {
        // Initialize graph nodes
        const initialNodes = data.nodes.map((n: any) => ({
          id: n.id,
          position: layoutMap[n.id] || { x: Math.random() * 500, y: Math.random() * 500 },
          data: { label: n.label },
          style: {
            background: n.type === 'agent' ? '#3B82F6' : '#10B981',
            color: '#fff',
            border: '1px solid #222',
            borderRadius: '8px',
            padding: '10px 15px',
            fontWeight: 'bold',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          },
        }));
        setNodes(initialNodes);
        addLog('Initialized Network Grid');
      } 
      else if (data.type === 'event') {
        addLog(`[${data.action.toUpperCase()}] ${data.message}`);

        if (data.action === 'read' || data.action === 'write') {
          // Flash nodes to indicate activity
          setNodes((nds) =>
            nds.map((node) => {
              if (node.id === data.source || node.id === data.target) {
                return {
                  ...node,
                  style: { ...node.style, background: '#F59E0B' }, // Flash orange
                };
              }
              // Reset other nodes to default color
              return {
                ...node,
                style: {
                  ...node.style,
                  background: node.id.startsWith('agent') ? '#3B82F6' : '#10B981',
                },
              };
            })
          );

          // Add animating Edge showing data transfer
          const newEdge = {
            id: `e-${data.source}-${data.target}-${Date.now()}`,
            source: data.source,
            target: data.target,
            animated: true,
            label: data.action,
            style: { stroke: data.action === 'write' ? '#EF4444' : '#6366F1', strokeWidth: 3 },
            markerEnd: { type: MarkerType.ArrowClosed },
          };
          setEdges((eds) => addEdge(newEdge as unknown as Edge, eds));
        }
      } 
      else if (data.type === 'complete') {
        addLog('Simulation Finished Successfully.');
        eventSource.close();
        setIsSimulating(false);
      }
      else if (data.type === 'error') {
        addLog(`[ERROR] ${data.message}`);
        eventSource.close();
        setIsSimulating(false);
      }
    };

    eventSource.onerror = (err) => {
      addLog('Connection to Simulation Backend Lost.');
      eventSource.close();
      setIsSimulating(false);
    };
  }, [setNodes, setEdges]);

  return (
    <div className="flex h-screen w-full bg-zinc-950 text-white overflow-hidden">
      {/* Visualizer Canvas */}
      <div className="flex-grow h-full relative border-r border-zinc-800">
        <h1 className="absolute top-4 left-4 z-10 text-2xl font-bold tracking-tight text-white drop-shadow-md">
          Agent Storage Flow Matrix
        </h1>
        
        <button
          onClick={startSimulation}
          disabled={isSimulating}
          className={`absolute top-4 right-4 z-10 px-6 py-2 rounded-md font-semibold transition-all ${
            isSimulating ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed' : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg'
          }`}
        >
          {isSimulating ? 'Simulating...' : 'Run Storage Mock'}
        </button>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          colorMode="dark"
        >
          <Background color="#333" gap={16} />
          <Controls />
          <MiniMap nodeColor={(n) => (n.style?.background as string) || '#fff'} />
        </ReactFlow>
      </div>

      {/* Live Event Log */}
      <div className="w-96 flex flex-col h-full bg-zinc-900 border-l border-zinc-800 shadow-xl">
        <div className="p-4 border-b border-zinc-800 bg-zinc-950">
          <h2 className="text-lg font-semibold text-emerald-400">Activity Telemetry</h2>
          <p className="text-xs text-zinc-500 mt-1">Real-time IO event stream</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-sm">
          {logs.map((log) => (
            <div key={log.id} className="p-2 bg-zinc-800/50 rounded border border-zinc-700/50 animate-in fade-in slide-in-from-right-2">
              <span className="text-zinc-400">{new Date().toISOString().split('T')[1].slice(0, 8)}</span>
              <span className="block mt-1 text-zinc-200">{log.text}</span>
            </div>
          ))}
          {logs.length === 0 && !isSimulating && (
            <div className="text-center text-zinc-500 mt-10 italic">Awaiting Simulation...</div>
          )}
        </div>
      </div>
    </div>
  );
}
