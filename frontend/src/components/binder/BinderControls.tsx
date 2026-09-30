import { useState } from "react";

import {
  useCreateBinder,
  useDeleteBinder,
  useSetDefaultBinder,
  useUpdateBinder,
} from "../../hooks/useBinders";
import { ApiError } from "../../api/client";
import {
  BINDER_LAYOUT_PRESETS,
  MAX_BINDER_DIMENSION,
  MIN_BINDER_DIMENSION,
} from "../../lib/constants";
import type { Binder, BinderType } from "../../types";

// ---------------------------------------------------------------------------
// Selector + actions bar
// ---------------------------------------------------------------------------

interface BinderControlsProps {
  binders: Binder[];
  selectedBinderId: number | null;
  onSelect: (binderId: number) => void;
}

export function BinderControls({ binders, selectedBinderId, onSelect }: BinderControlsProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [showManage, setShowManage] = useState(false);

  const selected = binders.find((b) => b.id === selectedBinderId) ?? null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <label className="sr-only" htmlFor="binder-selector">
        Select binder
      </label>
      <select
        id="binder-selector"
        value={selectedBinderId ?? ""}
        onChange={(e) => onSelect(Number(e.target.value))}
        className="px-3 py-1.5 border border-gray-300 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
      >
        {binders.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
            {b.is_default ? " (default)" : ""}
            {b.binder_type === "FREE_PLACEMENT" ? " — Free" : " — Pokédex"}
          </option>
        ))}
      </select>

      {selected?.is_default && (
        <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
          Default
        </span>
      )}

      <button
        onClick={() => setShowManage(true)}
        className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
      >
        Manage Binders
      </button>
      <button
        onClick={() => setShowCreate(true)}
        className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
      >
        + Create Binder
      </button>

      {showCreate && (
        <CreateBinderModal
          binders={binders}
          onClose={() => setShowCreate(false)}
          onCreated={(binder) => {
            setShowCreate(false);
            onSelect(binder.id);
          }}
        />
      )}
      {showManage && (
        <ManageBindersModal
          binders={binders}
          onClose={() => setShowManage(false)}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create modal
// ---------------------------------------------------------------------------

function CreateBinderModal({
  binders,
  onClose,
  onCreated,
}: {
  binders: Binder[];
  onClose: () => void;
  onCreated: (binder: Binder) => void;
}) {
  // A profile may only have one Pokédex binder. If one already exists, the
  // Pokédex type is unavailable and new binders must be Free Placement.
  const pokedexExists = binders.some((b) => b.binder_type === "POKEDEX");

  const [name, setName] = useState("");
  const [binderType, setBinderType] = useState<BinderType>(
    pokedexExists ? "FREE_PLACEMENT" : "POKEDEX",
  );
  const [rows, setRows] = useState(3);
  const [columns, setColumns] = useState(3);
  const [error, setError] = useState<string | null>(null);

  const createMut = useCreateBinder();

  function submit() {
    setError(null);
    if (!name.trim()) {
      setError("Please enter a binder name.");
      return;
    }
    createMut.mutate(
      { name: name.trim(), binder_type: binderType, rows, columns },
      {
        onSuccess: (binder) => onCreated(binder),
        onError: (err) => {
          if (err instanceof ApiError) {
            setError((err.body as { detail?: string })?.detail ?? "Failed to create binder.");
          } else {
            setError("Failed to create binder.");
          }
        },
      },
    );
  }

  return (
    <ModalShell title="Create Binder" onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="new-binder-name">
            Name
          </label>
          <input
            id="new-binder-name"
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="e.g. Master Collection"
          />
        </div>

        <div>
          <span className="block text-sm font-medium text-gray-700 mb-1">Type</span>
          {pokedexExists ? (
            <div className="space-y-1">
              <TypeButton label="Free Placement" active onClick={() => setBinderType("FREE_PLACEMENT")} />
              <p className="text-xs text-gray-500">
                A Pokédex binder already exists — a profile can only have one, so new
                binders are Free Placement.
              </p>
            </div>
          ) : (
            <div className="flex gap-2">
              <TypeButton
                label="Pokédex"
                active={binderType === "POKEDEX"}
                onClick={() => setBinderType("POKEDEX")}
              />
              <TypeButton
                label="Free Placement"
                active={binderType === "FREE_PLACEMENT"}
                onClick={() => setBinderType("FREE_PLACEMENT")}
              />
            </div>
          )}
        </div>

        <LayoutPicker
          rows={rows}
          columns={columns}
          onChange={(r, c) => {
            setRows(r);
            setColumns(c);
          }}
        />

        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={createMut.isPending}
            className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

// ---------------------------------------------------------------------------
// Manage modal
// ---------------------------------------------------------------------------

function ManageBindersModal({
  binders,
  onClose,
  onSelect,
}: {
  binders: Binder[];
  onClose: () => void;
  onSelect: (binderId: number) => void;
}) {
  const updateMut = useUpdateBinder();
  const deleteMut = useDeleteBinder();
  const defaultMut = useSetDefaultBinder();
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");

  const onlyOneBinder = binders.length <= 1;

  function startRename(binder: Binder) {
    setEditingId(binder.id);
    setEditName(binder.name);
  }

  function saveRename(binder: Binder) {
    updateMut.mutate(
      { binderId: binder.id, data: { name: editName.trim() } },
      {
        onSuccess: () => setEditingId(null),
        onError: (err) => setError(errText(err, "Failed to rename binder.")),
      },
    );
  }

  function changeLayout(binder: Binder, rows: number, columns: number) {
    setError(null);
    updateMut.mutate(
      { binderId: binder.id, data: { rows, columns } },
      { onError: (err) => setError(errText(err, "Failed to change layout.")) },
    );
  }

  function makeDefault(binder: Binder) {
    setError(null);
    defaultMut.mutate(binder.id, {
      onError: (err) => setError(errText(err, "Failed to set default.")),
    });
  }

  function remove(binder: Binder) {
    setError(null);
    deleteMut.mutate(binder.id, {
      onError: (err) => setError(errText(err, "Failed to delete binder.")),
    });
  }

  return (
    <ModalShell title="Manage Binders" onClose={onClose}>
      {error && (
        <p className="mb-3 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
      {onlyOneBinder && (
        <p className="mb-3 text-xs text-gray-500">
          You must create another binder before you can delete this one.
        </p>
      )}
      <ul className="space-y-3 max-h-[55vh] overflow-y-auto">
        {binders.map((binder) => (
          <li
            key={binder.id}
            className="border border-gray-200 rounded-lg p-3 space-y-2"
            data-testid={`manage-binder-${binder.id}`}
          >
            <div className="flex items-center justify-between gap-2">
              {editingId === binder.id ? (
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  maxLength={100}
                  className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                  aria-label={`Rename ${binder.name}`}
                />
              ) : (
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900">{binder.name}</span>
                  <span className="text-[10px] text-gray-500">
                    {binder.binder_type === "FREE_PLACEMENT" ? "Free Placement" : "Pokédex"}
                  </span>
                  {binder.is_default && (
                    <span className="text-[10px] font-medium text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
                      Default
                    </span>
                  )}
                </div>
              )}
              <div className="flex items-center gap-1">
                {editingId === binder.id ? (
                  <button
                    onClick={() => saveRename(binder)}
                    className="px-2 py-1 text-xs font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700"
                  >
                    Save
                  </button>
                ) : (
                  <button
                    onClick={() => startRename(binder)}
                    className="px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
                  >
                    Rename
                  </button>
                )}
                {!binder.is_default && (
                  <button
                    onClick={() => makeDefault(binder)}
                    className="px-2 py-1 text-xs font-medium text-indigo-700 bg-indigo-50 rounded hover:bg-indigo-100"
                  >
                    Set Default
                  </button>
                )}
                <button
                  onClick={() => remove(binder)}
                  disabled={onlyOneBinder}
                  title={onlyOneBinder ? "Create another binder first" : "Delete binder"}
                  className="px-2 py-1 text-xs font-medium text-red-700 bg-red-50 rounded hover:bg-red-100 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Delete
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-gray-500">Layout:</span>
              <LayoutPicker
                rows={binder.rows}
                columns={binder.columns}
                compact
                onChange={(r, c) => changeLayout(binder, r, c)}
              />
              <button
                onClick={() => {
                  onSelect(binder.id);
                  onClose();
                }}
                className="ml-auto text-xs font-medium text-indigo-600 hover:text-indigo-800"
              >
                Open
              </button>
            </div>
          </li>
        ))}
      </ul>
    </ModalShell>
  );
}

// ---------------------------------------------------------------------------
// Shared pieces
// ---------------------------------------------------------------------------

function LayoutPicker({
  rows,
  columns,
  onChange,
  compact = false,
}: {
  rows: number;
  columns: number;
  onChange: (rows: number, columns: number) => void;
  compact?: boolean;
}) {
  const dims = [];
  for (let d = MIN_BINDER_DIMENSION; d <= MAX_BINDER_DIMENSION; d++) dims.push(d);

  return (
    <div className={compact ? "flex items-center gap-2" : "space-y-2"}>
      {!compact && <span className="block text-sm font-medium text-gray-700">Layout</span>}
      {!compact && (
        <div className="flex flex-wrap gap-1.5">
          {BINDER_LAYOUT_PRESETS.map((p) => {
            const active = p.rows === rows && p.columns === columns;
            return (
              <button
                key={p.label}
                onClick={() => onChange(p.rows, p.columns)}
                className={`px-2 py-1 text-xs rounded border ${
                  active
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                }`}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      )}
      <div className="flex items-center gap-2 text-sm">
        <select
          value={rows}
          onChange={(e) => onChange(Number(e.target.value), columns)}
          className="px-2 py-1 border border-gray-300 rounded text-sm"
          aria-label="Rows"
        >
          {dims.map((d) => (
            <option key={d} value={d}>
              {d} rows
            </option>
          ))}
        </select>
        <span className="text-gray-400">×</span>
        <select
          value={columns}
          onChange={(e) => onChange(rows, Number(e.target.value))}
          className="px-2 py-1 border border-gray-300 rounded text-sm"
          aria-label="Columns"
        >
          {dims.map((d) => (
            <option key={d} value={d}>
              {d} cols
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function TypeButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-sm rounded-md border ${
        active
          ? "bg-indigo-600 text-white border-indigo-600"
          : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
      }`}
    >
      {label}
    </button>
  );
}

function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="Close">
            ✕
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

function errText(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return (err.body as { detail?: string })?.detail ?? fallback;
  }
  return fallback;
}
