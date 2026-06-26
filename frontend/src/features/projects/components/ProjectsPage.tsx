import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, Plus, ChevronRight } from 'lucide-react';
import { useAuthStore } from '@/features/auth';
import { requestTypeLabel } from '@/shared/constants/requestTypes';
import { Project } from '@/shared/types';
import { useProjectStore } from '../store';
import { CreateProjectModal } from './CreateProjectModal';
import { WaterCoolerChibis } from './WaterCoolerChibis';
import './ProjectsPage.css';

export function ProjectsPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { projects, isLoading, fetchProjects } = useProjectStore();
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (user) fetchProjects();
  }, [fetchProjects, user]);

  // Group children under their parents for one-level nesting display.
  const { topLevel, childrenByParent } = useMemo(() => {
    const topLevel: Project[] = [];
    const childrenByParent: Record<string, Project[]> = {};
    for (const p of projects) {
      if (p.parent_project_id) {
        (childrenByParent[p.parent_project_id] ??= []).push(p);
      } else {
        topLevel.push(p);
      }
    }
    return { topLevel, childrenByParent };
  }, [projects]);

  return (
    <div className="projects-page">
      <div className="projects-header">
        <div>
          <h1 className="projects-title">Hubspaces</h1>
          <p className="projects-subtitle">Organize your requests into themed hubspaces.</p>
        </div>
        <button className="projects-new-btn" onClick={() => setShowCreate(true)}>
          <Plus size={16} />
          <span>New hubspace</span>
        </button>
      </div>

      {isLoading && projects.length === 0 ? (
        <div className="projects-loading"><div className="spinner" /></div>
      ) : projects.length === 0 ? (
        <div className="projects-empty">
          <WaterCoolerChibis />
          <h2>No hubspaces yet</h2>
          <p>Create a hubspace to group related requests and lock them to a request type.</p>
          <button className="projects-new-btn" onClick={() => setShowCreate(true)}>
            <Plus size={16} />
            <span>New hubspace</span>
          </button>
        </div>
      ) : (
        <div className="projects-grid">
          {topLevel.map(project => (
            <ProjectCard
              key={project.id}
              project={project}
              children={childrenByParent[project.id] ?? []}
              onOpen={id => navigate(`/hubspaces/${id}`)}
            />
          ))}
        </div>
      )}

      <CreateProjectModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={p => navigate(`/hubspaces/${p.id}`)}
      />
    </div>
  );
}

interface ProjectCardProps {
  project: Project;
  children: Project[];
  onOpen: (id: string) => void;
}

function ProjectCard({ project, children, onOpen }: ProjectCardProps) {
  return (
    <div className="project-card" onClick={() => onOpen(project.id)} role="button" tabIndex={0}>
      <div className="project-card-icon"><FolderKanban size={20} /></div>
      <div className="project-card-body">
        <h3 className="project-card-name">{project.name}</h3>
        {project.instructions && (
          <p className="project-card-instructions">{project.instructions}</p>
        )}
        <span className="project-card-type">
          {requestTypeLabel(project.locked_intent, project.locked_service_type)}
        </span>
        {children.length > 0 && (
          <div className="project-card-children">
            {children.map(c => (
              <button
                key={c.id}
                className="project-card-child"
                onClick={e => { e.stopPropagation(); onOpen(c.id); }}
              >
                <ChevronRight size={13} />
                <span>{c.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
