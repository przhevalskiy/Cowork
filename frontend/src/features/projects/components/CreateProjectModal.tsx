import { useState } from 'react';
import { Modal } from '@/components/ui';
import { Project } from '@/shared/types';
import { REQUEST_TYPES, findRequestType } from '@/shared/constants/requestTypes';
import { useProjectStore } from '../store';
import './CreateProjectModal.css';

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (project: Project) => void;
  /** When provided, edits an existing project instead of creating one. */
  project?: Project;
}

export function CreateProjectModal({ isOpen, onClose, onCreated, project }: CreateProjectModalProps) {
  const { projects, createProject, updateProject } = useProjectStore();
  const isEdit = !!project;

  const [name, setName] = useState(project?.name ?? '');
  const [instructions, setInstructions] = useState(project?.instructions ?? '');
  const [requestTypeIdx, setRequestTypeIdx] = useState<number>(() => {
    const rt = findRequestType(project?.locked_intent, project?.locked_service_type);
    return rt ? REQUEST_TYPES.indexOf(rt) : 0;
  });
  const [parentId, setParentId] = useState<string>(project?.parent_project_id ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Single-level nesting: only top-level projects (no parent) can be parents,
  // and a project being edited can't parent itself.
  const parentOptions = projects.filter(
    p => !p.parent_project_id && p.id !== project?.id
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Please give the hubspace a name.');
      return;
    }
    setSubmitting(true);
    setError(null);
    const rt = REQUEST_TYPES[requestTypeIdx];
    const payload = {
      name: name.trim(),
      instructions: instructions.trim() || null,
      locked_intent: rt.intent,
      locked_service_type: rt.serviceType ?? null,
      parent_project_id: parentId || null,
    };
    try {
      if (isEdit && project) {
        await updateProject(project.id, payload);
        onClose();
      } else {
        const created = await createProject(payload);
        onCreated?.(created);
        onClose();
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEdit ? 'Edit hubspace' : 'New hubspace'} size="md">
      <form className="create-project-form" onSubmit={handleSubmit}>
        <label className="cp-field">
          <span className="cp-label">Name</span>
          <input
            className="cp-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. DSS Events"
            autoFocus
          />
        </label>

        <label className="cp-field">
          <span className="cp-label">Instructions <span className="cp-hint">(the hubspace's theme / brief)</span></span>
          <textarea
            className="cp-input cp-textarea"
            value={instructions}
            onChange={e => setInstructions(e.target.value)}
            placeholder="Focus on… best practices… anything tasks in this hubspace should follow."
            rows={4}
          />
        </label>

        <label className="cp-field">
          <span className="cp-label">Request type <span className="cp-hint">(tasks are locked to this)</span></span>
          <select
            className="cp-input"
            value={requestTypeIdx}
            onChange={e => setRequestTypeIdx(Number(e.target.value))}
          >
            {REQUEST_TYPES.map((rt, i) => (
              <option key={rt.label} value={i}>{rt.label}</option>
            ))}
          </select>
        </label>

        <label className="cp-field">
          <span className="cp-label">Parent hubspace <span className="cp-hint">(optional)</span></span>
          <select
            className="cp-input"
            value={parentId}
            onChange={e => setParentId(e.target.value)}
          >
            <option value="">None (top-level)</option>
            {parentOptions.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>

        {error && <p className="cp-error">{error}</p>}

        <div className="cp-actions">
          <button type="button" className="cp-btn cp-btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="cp-btn cp-btn-primary" disabled={submitting}>
            {submitting ? 'Saving…' : isEdit ? 'Save changes' : 'Create hubspace'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
