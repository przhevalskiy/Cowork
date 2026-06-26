import { useEffect, useRef, useState } from 'react';
import { FileText, Upload, Trash2, Loader2 } from 'lucide-react';
import { ProjectFile } from '@/shared/types';
import { api } from '@/shared/services/api';

interface ProjectFilesPanelProps {
  projectId: string;
}

export function ProjectFilesPanel({ projectId }: ProjectFilesPanelProps) {
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      setFiles(await api.getProjectFiles(projectId));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [projectId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const created = await api.uploadProjectFile(projectId, file);
      setFiles(prev => [created, ...prev]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const handleDelete = async (fileId: string) => {
    try {
      await api.deleteProjectFile(projectId, fileId);
      setFiles(prev => prev.filter(f => f.id !== fileId));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="pd-rail-card">
      <div className="pd-rail-head">
        <h3 className="pd-rail-title"><FileText size={15} /> Files &amp; sources</h3>
        <button
          className="pd-rail-add"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          title="Upload file"
        >
          {uploading ? <Loader2 size={15} className="pd-spin" /> : <Upload size={15} />}
        </button>
        <input ref={inputRef} type="file" hidden onChange={handleUpload} />
      </div>
      <p className="pd-rail-body">Shared across all tasks in this hubspace.</p>

      {error && <p className="pd-rail-error">{error}</p>}

      {files.length > 0 && (
        <ul className="pd-file-list">
          {files.map(f => (
            <li key={f.id} className="pd-file-item">
              <FileText size={14} className="pd-file-icon" />
              <span className="pd-file-name" title={f.filename}>{f.filename}</span>
              <button className="pd-file-del" onClick={() => handleDelete(f.id)} title="Remove">
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
