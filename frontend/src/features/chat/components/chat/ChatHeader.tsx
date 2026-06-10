import { useState, useEffect } from 'react';
import { Download, Paperclip } from 'lucide-react';
import { AttachmentPanel } from '../attachments/AttachmentPanel';
import { FilePreviewModal } from '../attachments/FilePreviewModal';
import ExportDropdown from '../ui/ExportDropdown';
import { useChatStore } from '../../store';
import { useAttachmentStore } from '@/features/attachments/store';
import './ChatHeader.css';

interface ChatHeaderProps {
  discussionId: string;
  discussionTitle: string;
}

export function ChatHeader({ discussionId, discussionTitle }: ChatHeaderProps) {
  const [showAttachments, setShowAttachments] = useState(false);
  const { messages } = useChatStore();
  const { attachments, fetchAttachments, reset } = useAttachmentStore();

  useEffect(() => {
    reset();
    if (discussionId) {
      fetchAttachments(discussionId);
    }
  }, [discussionId, fetchAttachments, reset]);

  return (
    <>
      <div className="chat-header">
        <div className="chat-header-actions">
          <button
            className="chat-header-btn"
            onClick={() => setShowAttachments(!showAttachments)}
            title="Conversation attachments"
          >
            <Paperclip size={18} />
            <span className="visually-hidden">Attachments</span>
            {attachments.length > 0 && (
              <span className="chat-header-badge">{attachments.length}</span>
            )}
          </button>

          <ExportDropdown
            mode="conversation"
            messages={messages}
            title={discussionTitle || 'Cowork Conversation'}
          >
            {(_open, toggle) => (
              <button
                className="chat-header-btn"
                onClick={toggle}
                disabled={messages.length === 0}
                title="Download conversation"
              >
                <Download size={18} />
                <span className="visually-hidden">Download</span>
              </button>
            )}
          </ExportDropdown>
        </div>

        {showAttachments && (
          <AttachmentPanel
            discussionId={discussionId}
            isOpen={showAttachments}
            onClose={() => setShowAttachments(false)}
          />
        )}
      </div>

      <FilePreviewModal />
    </>
  );
}
