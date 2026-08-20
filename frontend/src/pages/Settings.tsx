import { useState } from "react";
import {
  useActiveProfile,
  useCreateProfile,
  useDeleteProfile,
  useProfiles,
  useRenameProfile,
  useSwitchProfile,
  useUpdateProfileSettings,
} from "../hooks/useProfiles";
import { exportCollection, importCollection, createBackup, restoreBackup } from "../api/data";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ErrorState } from "../components/ErrorState";
import type { ExportResponse, ImportResponse, ProfileRead } from "../types";

export function Settings() {
  const { data: profiles, isLoading: profilesLoading } = useProfiles();
  const { data: activeProfile, isLoading: activeLoading } = useActiveProfile();

  if (profilesLoading || activeLoading) return <LoadingSpinner message="Loading settings..." />;
  if (!profiles || !activeProfile) return <ErrorState message="Failed to load settings." />;

  return (
    <div className="space-y-8 max-w-3xl">
      <h2 className="text-2xl font-bold">Settings</h2>

      <ProfileSection profiles={profiles} activeProfile={activeProfile} />
      <BinderSection activeProfile={activeProfile} />
      <DataSection />
      <AboutSection />
    </div>
  );
}

// ===========================================================================
// PROFILE SECTION
// ===========================================================================

function ProfileSection({ profiles, activeProfile }: { profiles: ProfileRead[]; activeProfile: ProfileRead }) {
  const switchProfile = useSwitchProfile();
  const createProfile = useCreateProfile();
  const renameProfile = useRenameProfile();
  const deleteProfile = useDeleteProfile();

  const [newName, setNewName] = useState("");
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const handleCreate = () => {
    if (!newName.trim()) return;
    setError("");
    createProfile.mutate({ name: newName.trim() }, {
      onSuccess: () => setNewName(""),
      onError: (e) => setError(e.message),
    });
  };

  const handleRename = (id: number) => {
    if (!renameValue.trim()) return;
    setError("");
    renameProfile.mutate({ profileId: id, data: { name: renameValue.trim() } }, {
      onSuccess: () => setRenamingId(null),
      onError: (e) => setError(e.message),
    });
  };

  const handleDelete = (id: number) => {
    setError("");
    deleteProfile.mutate(id, {
      onSuccess: () => setDeletingId(null),
      onError: (e) => setError(e.message),
    });
  };

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Profile</h3>
        <p className="text-sm text-gray-500 mt-0.5">
          Local profiles keep collections separate on this computer. These are not online accounts.
        </p>
      </div>

      {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">{error}</p>}

      {/* Current profile */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Active:</span>
        <span className="font-semibold text-indigo-600">{activeProfile.name}</span>
      </div>

      {/* Profile list */}
      <div className="space-y-2">
        {profiles.map((p) => (
          <div key={p.id} className={`flex items-center gap-3 p-2 rounded-md ${p.is_active ? "bg-indigo-50 border border-indigo-200" : "bg-gray-50 border border-gray-200"}`}>
            {renamingId === p.id ? (
              <div className="flex-1 flex gap-2">
                <input
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleRename(p.id)}
                  className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
                  autoFocus
                />
                <button onClick={() => handleRename(p.id)} className="text-xs font-medium text-indigo-600 hover:text-indigo-800">Save</button>
                <button onClick={() => setRenamingId(null)} className="text-xs text-gray-500">Cancel</button>
              </div>
            ) : (
              <>
                <span className={`flex-1 text-sm font-medium ${p.is_active ? "text-indigo-700" : "text-gray-700"}`}>
                  {p.name}
                  {p.is_active && <span className="ml-2 text-xs text-indigo-500">(active)</span>}
                </span>
                {!p.is_active && (
                  <button
                    onClick={() => switchProfile.mutate(p.id)}
                    disabled={switchProfile.isPending}
                    className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                  >
                    Switch
                  </button>
                )}
                <button
                  onClick={() => { setRenamingId(p.id); setRenameValue(p.name); }}
                  className="text-xs text-gray-500 hover:text-gray-700"
                >
                  Rename
                </button>
                {profiles.length > 1 && (
                  deletingId === p.id ? (
                    <div className="flex gap-1">
                      <button onClick={() => handleDelete(p.id)} className="text-xs font-medium text-red-600 hover:text-red-800">Confirm Delete</button>
                      <button onClick={() => setDeletingId(null)} className="text-xs text-gray-500">Cancel</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeletingId(p.id)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Delete
                    </button>
                  )
                )}
              </>
            )}
          </div>
        ))}
      </div>

      {/* Create new profile */}
      <div className="flex gap-2 pt-2 border-t border-gray-100">
        <input
          type="text"
          placeholder="New profile name..."
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <button
          onClick={handleCreate}
          disabled={!newName.trim() || createProfile.isPending}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          Create
        </button>
      </div>

      {deletingId && (
        <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded">
          Warning: Deleting a profile permanently removes its collection data.
        </p>
      )}
    </section>
  );
}

// ===========================================================================
// BINDER SECTION
// ===========================================================================

function BinderSection({ activeProfile }: { activeProfile: ProfileRead }) {
  const updateSettings = useUpdateProfileSettings();
  const [rows, setRows] = useState(activeProfile.binder_rows);
  const [cols, setCols] = useState(activeProfile.binder_columns);
  const [sort, setSort] = useState(activeProfile.binder_sort);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    updateSettings.mutate(
      { profileId: activeProfile.id, data: { binder_rows: rows, binder_columns: cols, binder_sort: sort } },
      { onSuccess: () => { setSaved(true); setTimeout(() => setSaved(false), 2000); } },
    );
  };

  const hasChanges = rows !== activeProfile.binder_rows || cols !== activeProfile.binder_columns || sort !== activeProfile.binder_sort;

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Binder</h3>
        <p className="text-sm text-gray-500 mt-0.5">Configure how cards are arranged in your digital binder.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Rows</label>
          <select value={rows} onChange={(e) => setRows(Number(e.target.value))} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
            {[2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Columns</label>
          <select value={cols} onChange={(e) => setCols(Number(e.target.value))} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
            {[2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Sort</label>
          <select value={sort} onChange={(e) => setSort(e.target.value)} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
            <option value="dex_number">Dex Number</option>
            <option value="set">Set</option>
            <option value="card_number">Card Number</option>
            <option value="recent">Recently Added</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={!hasChanges || updateSettings.isPending}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {updateSettings.isPending ? "Saving..." : "Save Changes"}
        </button>
        {saved && <span className="text-sm text-green-600 font-medium">Saved!</span>}
        <span className="text-xs text-gray-400 ml-auto">Layout: {rows}×{cols} = {rows * cols} cards per page</span>
      </div>
    </section>
  );
}

// ===========================================================================
// DATA SECTION
// ===========================================================================

function DataSection() {
  const [exportData, setExportData] = useState<ExportResponse | null>(null);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [importMode, setImportMode] = useState<"new_profile" | "replace" | "merge">("replace");
  const [importFile, setImportFile] = useState<ExportResponse | null>(null);
  const [importFileName, setImportFileName] = useState("");
  const [backupResult, setBackupResult] = useState<string | null>(null);
  const [restorePath, setRestorePath] = useState("");
  const [restoreResult, setRestoreResult] = useState<{ success: boolean; message?: string | null } | null>(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  const handleExport = async () => {
    setError("");
    setLoading("export");
    try {
      const data = await exportCollection();
      setExportData(data);
      // Trigger download
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${data.profile.name}_collection.pulldex`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message || "Export failed.");
    } finally {
      setLoading("");
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportFileName(file.name);
    setError("");
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = JSON.parse(event.target?.result as string);
        if (!data.format_version || !data.collection) {
          setError("Invalid .pulldex file: missing required fields.");
          setImportFile(null);
          return;
        }
        setImportFile(data);
      } catch {
        setError("Invalid file: could not parse JSON.");
        setImportFile(null);
      }
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!importFile) return;
    setError("");
    setLoading("import");
    try {
      const result = await importCollection({ data: importFile, mode: importMode });
      setImportResult(result);
      setImportFile(null);
      setImportFileName("");
    } catch (e: any) {
      setError(e.message || "Import failed.");
    } finally {
      setLoading("");
    }
  };

  const handleBackup = async () => {
    setError("");
    setLoading("backup");
    try {
      const result = await createBackup();
      if (result.success) {
        setBackupResult(result.backup_path);
      } else {
        setError(result.error || "Backup failed.");
      }
    } catch (e: any) {
      setError(e.message || "Backup failed.");
    } finally {
      setLoading("");
    }
  };

  const handleRestore = async () => {
    if (!restorePath.trim()) return;
    setError("");
    setLoading("restore");
    try {
      const result = await restoreBackup({ backup_path: restorePath.trim() });
      setRestoreResult(result);
    } catch (e: any) {
      const detail = e.body?.detail;
      if (detail?.errors) {
        setError(detail.errors.join("; "));
      } else {
        setError(e.message || "Restore failed.");
      }
    } finally {
      setLoading("");
    }
  };

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-5 space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Data Management</h3>
        <p className="text-sm text-gray-500 mt-0.5">Export, import, backup and restore your collection data.</p>
      </div>

      {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">{error}</p>}

      {/* Export/Import */}
      <div className="space-y-3 border-b border-gray-100 pb-4">
        <h4 className="text-sm font-semibold text-gray-700">Collection Export / Import</h4>
        <p className="text-xs text-gray-500">Export your profile's collection as a portable .pulldex file that can be imported on another computer or profile.</p>

        <button
          onClick={handleExport}
          disabled={loading === "export"}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading === "export" ? "Exporting..." : "Export Collection"}
        </button>

        {exportData && (
          <p className="text-xs text-green-600">
            Exported {exportData.collection.length} entries from "{exportData.profile.name}".
          </p>
        )}

        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-3">
            <label className="px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer">
              Choose .pulldex file
              <input type="file" accept=".pulldex,.json" onChange={handleFileSelect} className="hidden" />
            </label>
            {importFileName && <span className="text-sm text-gray-600">{importFileName}</span>}
          </div>

          {importFile && (
            <div className="space-y-2 bg-gray-50 p-3 rounded-md">
              <p className="text-sm text-gray-700">
                Ready to import <strong>{importFile.collection.length}</strong> entries from "{importFile.profile.name}".
              </p>
              <div className="flex items-center gap-3">
                <select
                  value={importMode}
                  onChange={(e) => setImportMode(e.target.value as "new_profile" | "replace" | "merge")}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
                >
                  <option value="replace">Import &amp; Replace</option>
                  <option value="merge">Import &amp; Merge</option>
                  <option value="new_profile">Import as new profile</option>
                </select>
                <button
                  onClick={handleImport}
                  disabled={loading === "import"}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  {loading === "import" ? "Importing..." : "Import"}
                </button>
              </div>
              <p className="text-xs text-gray-500">
                {importMode === "replace"
                  ? "Replaces your current collection with the imported data. An automatic backup is created first. Importing the same file again produces the same result."
                  : importMode === "merge"
                  ? "Adds imported cards to your current collection. Quantities are combined for cards you already own."
                  : "Creates a new profile with the imported data. Your current profile is unchanged."}
              </p>
            </div>
          )}

          {importResult && (
            <div className="bg-green-50 border border-green-200 rounded-md p-3 text-sm space-y-1">
              <p className="font-medium text-green-700">Import complete!</p>
              <p className="text-green-600">Imported: {importResult.total_imported} ({importResult.imported_species} species, {importResult.imported_cards} cards)</p>
              {importResult.total_skipped > 0 && (
                <p className="text-yellow-600">Skipped: {importResult.total_skipped}</p>
              )}
              {importResult.warnings.length > 0 && (
                <details className="text-xs text-gray-600">
                  <summary className="cursor-pointer">Warnings ({importResult.warnings.length})</summary>
                  <ul className="mt-1 pl-4 list-disc">
                    {importResult.warnings.slice(0, 10).map((w, i) => <li key={i}>{w}</li>)}
                    {importResult.warnings.length > 10 && <li>...and {importResult.warnings.length - 10} more</li>}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Backup/Restore */}
      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-gray-700">Database Backup / Restore</h4>
        <p className="text-xs text-gray-500">
          Create a complete backup of the PullDex database, including all profiles and reference data.
          This is different from collection export — it backs up everything.
        </p>

        <button
          onClick={handleBackup}
          disabled={loading === "backup"}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading === "backup" ? "Creating Backup..." : "Create Backup"}
        </button>

        {backupResult && (
          <p className="text-xs text-green-600">Backup saved to: {backupResult}</p>
        )}

        <div className="mt-3 space-y-2 pt-3 border-t border-gray-100">
          <p className="text-xs text-red-600 font-medium">
            Restore replaces your entire database. All current data will be overwritten.
            An automatic backup is created before restoring.
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Path to backup .db file..."
              value={restorePath}
              onChange={(e) => setRestorePath(e.target.value)}
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400"
            />
            <button
              onClick={handleRestore}
              disabled={!restorePath.trim() || loading === "restore"}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50"
            >
              {loading === "restore" ? "Restoring..." : "Restore"}
            </button>
          </div>
          {restoreResult?.success && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 text-sm space-y-2">
              <p className="font-medium text-yellow-700">Database restored successfully!</p>
              <p className="text-yellow-600">{restoreResult.message}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 text-sm font-medium text-white bg-yellow-600 rounded-md hover:bg-yellow-700"
              >
                Restart PullDex
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// ===========================================================================
// ABOUT SECTION
// ===========================================================================

function AboutSection() {
  return (
    <section className="bg-white rounded-lg border border-gray-200 p-5 space-y-2">
      <h3 className="text-lg font-semibold text-gray-900">About</h3>
      <div className="text-sm text-gray-600 space-y-1">
        <p><strong>PullDex</strong> — Pokémon TCG Living Pokédex Completion Optimizer</p>
        <p>Version: 0.2.0</p>
        <p>Track your collection, get pack recommendations, and fill your Pokédex.</p>
      </div>
    </section>
  );
}
