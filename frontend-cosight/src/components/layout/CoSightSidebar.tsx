/**
 * CoSight Sidebar — mirrors Cowork's Sidebar exactly:
 * - Same 260px width + collapsible with PanelLeft/PanelLeftClose
 * - Same resize-handle click-to-expand
 * - New Chat button + nav links (icons only when collapsed)
 * - Conversations section with discussion list + date grouping
 * - ConversationItem with MoreVertical menu (delete, copy)
 */
import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, NavLink } from 'react-router-dom';
import {
  SquarePen, PanelLeftClose, PanelLeft,
  MoreVertical, Trash2, Copy, Check, MessageCirclePlus,
  LayoutDashboard, Globe, Search, Mail, Share2, FileText, MessageSquare,
} from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import './CoSightSidebar.css';

// ── Nav items ────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { path: '/',        label: 'Overview', icon: LayoutDashboard, end: true },
  { path: '/web',     label: 'Web',      icon: Globe },
  { path: '/seo',     label: 'Search',   icon: Search },
  { path: '/email',   label: 'Email',    icon: Mail },
  { path: '/social',  label: 'Social',   icon: Share2 },
  { path: '/reports', label: 'Reports',  icon: FileText },
];

// ── Date grouping ─────────────────────────────────────────────────────────────
interface DiscussionLike {
  id: string;
  title: string;
  updated_at: string;
}

function groupByDate(items: DiscussionLike[]) {
  const now = new Date();
  const todayStart     = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86400000);
  const weekStart      = new Date(todayStart.getTime() - 7 * 86400000);

  const today: DiscussionLike[]    = [];
  const yesterday: DiscussionLike[]= [];
  const week: DiscussionLike[]     = [];
  const older: DiscussionLike[]    = [];

  items.forEach(d => {
    const t = new Date(d.updated_at).getTime();
    if      (t >= todayStart.getTime())     today.push(d);
    else if (t >= yesterdayStart.getTime()) yesterday.push(d);
    else if (t >= weekStart.getTime())      week.push(d);
    else                                    older.push(d);
  });

  return { today, yesterday, week, older };
}

// ── ConversationItem ──────────────────────────────────────────────────────────
interface ConvItemProps {
  discussion: DiscussionLike;
  isActive: boolean;
  isCollapsed: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

function ConversationItem({ discussion, isActive, isCollapsed, onSelect, onDelete }: ConvItemProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});
  const [copied, setCopied] = useState(false);
  const btnRef  = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!showMenu) return;
    const handler = (e: MouseEvent) => {
      if (
        btnRef.current?.contains(e.target as Node) ||
        menuRef.current?.contains(e.target as Node)
      ) return;
      setShowMenu(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showMenu]);

  const handleMenuToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setMenuStyle({ position: 'fixed', top: rect.bottom + 4, right: window.innerWidth - rect.right, zIndex: 9999 });
    setShowMenu(v => !v);
  };

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(`${window.location.origin}/chat`);
    setCopied(true);
    setTimeout(() => { setCopied(false); setShowMenu(false); }, 1500);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete();
    setShowMenu(false);
  };

  if (isCollapsed) {
    return (
      <div className={`conversation-item ${isActive ? 'active' : ''}`} onClick={onSelect} title={discussion.title}>
        <MessageCirclePlus size={16} className="conversation-item-icon" />
      </div>
    );
  }

  return (
    <div className={`conversation-item ${isActive ? 'active' : ''}`} onClick={onSelect}>
      <span className="conversation-item-title">{discussion.title}</span>
      <div className="conversation-item-menu-container">
        <button ref={btnRef} className="conversation-item-menu-btn" onClick={handleMenuToggle}>
          <MoreVertical size={14} />
        </button>
        {showMenu && createPortal(
          <div ref={menuRef} className="conversation-menu" style={menuStyle}>
            <button className="conversation-menu-item" onClick={handleCopy}>
              <Copy size={14} />
              <span>{copied ? 'Copied!' : 'Copy link'}</span>
            </button>
            <button className="conversation-menu-item delete" onClick={handleDelete}>
              <Trash2 size={14} />
              <span>Delete</span>
            </button>
          </div>,
          document.body
        )}
      </div>
    </div>
  );
}

// ── ConversationGroup ────────────────────────────────────────────────────────
interface GroupProps {
  title: string;
  items: DiscussionLike[];
  activeId: string | null;
  isCollapsed: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

function ConversationGroup({ title, items, activeId, isCollapsed, onSelect, onDelete }: GroupProps) {
  if (items.length === 0) return null;
  return (
    <div className="conversation-group">
      {!isCollapsed && <h3 className="conversation-group-title">{title}</h3>}
      <div className="conversation-group-list">
        {items.map(d => (
          <ConversationItem
            key={d.id}
            discussion={d}
            isActive={d.id === activeId}
            isCollapsed={isCollapsed}
            onSelect={() => onSelect(d.id)}
            onDelete={() => onDelete(d.id)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Main Sidebar ─────────────────────────────────────────────────────────────
export const CoSightSidebar: React.FC = () => {
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const {
    discussions,
    activeDiscussionId,
    loadDiscussions,
    createDiscussion,
    setActiveDiscussion,
  } = useChatStore();

  // Delete a discussion — add to store if not already there
  const deleteDiscussion = async (id: string) => {
    try {
      await fetch(`/api/cosight/chat/discussions/${id}`, { method: 'DELETE' });
      // Reload list
      await loadDiscussions();
      if (activeDiscussionId === id) {
        setActiveDiscussion(null);
        navigate('/chat');
      }
    } catch (e) {
      console.error('Delete discussion failed', e);
    }
  };

  useEffect(() => {
    loadDiscussions();
  }, []);

  const handleNewChat = () => {
    setActiveDiscussion(null);
    navigate('/chat');
  };

  const handleSelectDiscussion = (id: string) => {
    setActiveDiscussion(id);
    navigate('/chat');
  };

  const grouped = groupByDate(discussions);

  return (
    <aside
      className={`cs-sidebar ${isCollapsed ? 'collapsed' : ''}`}
      onClick={(e) => {
        if (!isCollapsed) return;
        if ((e.target as HTMLElement).closest('button, a, [role="button"]')) return;
        setIsCollapsed(false);
      }}
    >
      {/* ── Header ── */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          {!isCollapsed && <span className="sidebar-logo-wordmark">Cosight</span>}
        </div>
        <button
          className="sidebar-collapse-btn"
          onClick={() => setIsCollapsed(v => !v)}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      {/* ── Nav links ── */}
      <div className="sidebar-nav-links">
        {/* New Chat */}
        <button className="sidebar-nav-link" onClick={handleNewChat}>
          <SquarePen size={18} />
          {!isCollapsed && <span>New Chat</span>}
        </button>

        {/* Dashboard pages */}
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.end}
            className={({ isActive }) =>
              `sidebar-nav-link${isActive ? ' active' : ''}`
            }
          >
            <item.icon size={18} />
            {!isCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </div>

      {/* ── Conversations header ── */}
      {!isCollapsed && (
        <div className="conversations-header">
          <h3 className="sidebar-section-title">Conversations</h3>
        </div>
      )}

      {/* ── Conversations list ── */}
      <div className="sidebar-conversations">
        <ConversationGroup
          title="Today"
          items={grouped.today}
          activeId={activeDiscussionId}
          isCollapsed={isCollapsed}
          onSelect={handleSelectDiscussion}
          onDelete={deleteDiscussion}
        />
        <ConversationGroup
          title="Yesterday"
          items={grouped.yesterday}
          activeId={activeDiscussionId}
          isCollapsed={isCollapsed}
          onSelect={handleSelectDiscussion}
          onDelete={deleteDiscussion}
        />
        <ConversationGroup
          title="Previous 7 days"
          items={grouped.week}
          activeId={activeDiscussionId}
          isCollapsed={isCollapsed}
          onSelect={handleSelectDiscussion}
          onDelete={deleteDiscussion}
        />
        <ConversationGroup
          title="Older"
          items={grouped.older}
          activeId={activeDiscussionId}
          isCollapsed={isCollapsed}
          onSelect={handleSelectDiscussion}
          onDelete={deleteDiscussion}
        />
      </div>

      {/* ── Footer ── */}
      <div className="sidebar-footer">
        {!isCollapsed && <span className="sidebar-cbs-label">CBS MarComm</span>}
      </div>

      {/* ── Resize handle ── */}
      <div
        className="sidebar-resize-handle"
        onClick={() => setIsCollapsed(v => !v)}
        title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      />
    </aside>
  );
};
