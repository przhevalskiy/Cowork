import { useState, useEffect } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { useAuthStore } from '@/features/auth';
import { supabase } from '@/shared/services/supabase';
import { AVATAR_ICONS, getAvatarIcon } from '@/shared/constants/avatarIcons';
import './AccountSettingsModal.css';

interface AccountSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AccountSettingsModal({ isOpen, onClose }: AccountSettingsModalProps) {
  const { user } = useAuthStore();

  const [displayName, setDisplayName] = useState('');
  const [preferredName, setPreferredName] = useState('');
  const [selectedAvatar, setSelectedAvatar] = useState('user');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [savingPreferred, setSavingPreferred] = useState(false);
  const [savedPreferred, setSavedPreferred] = useState(false);
  const [savingAvatar, setSavingAvatar] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync form state when modal opens or user changes
  useEffect(() => {
    if (isOpen && user) {
      setDisplayName(user.user_metadata?.display_name || '');
      setPreferredName(user.user_metadata?.preferred_name || '');
      setSelectedAvatar(user.user_metadata?.avatar_icon || 'user');
      setSaved(false);
      setSavedPreferred(false);
      setError(null);
    }
  }, [isOpen, user]);

  const handleSaveProfile = async () => {
    if (!displayName.trim()) return;
    setSaving(true);
    setError(null);

    const { error: updateError } = await supabase.auth.updateUser({
      data: { display_name: displayName.trim() },
    });

    if (updateError) {
      setError(updateError.message);
    } else {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
    setSaving(false);
  };

  const handleSelectAvatar = async (avatarId: string) => {
    setSelectedAvatar(avatarId);
    setSavingAvatar(true);
    setError(null);

    const { error: updateError } = await supabase.auth.updateUser({
      data: { avatar_icon: avatarId },
    });

    if (updateError) {
      setError(updateError.message);
    }
    setSavingAvatar(false);
  };

  const handleSavePreferredName = async () => {
    setSavingPreferred(true);
    setError(null);

    const { error: updateError } = await supabase.auth.updateUser({
      data: { preferred_name: preferredName.trim() },
    });

    if (updateError) {
      setError(updateError.message);
    } else {
      setSavedPreferred(true);
      setTimeout(() => setSavedPreferred(false), 2000);
    }
    setSavingPreferred(false);
  };

  const hasChanges = displayName.trim() !== (user?.user_metadata?.display_name || '');
  const hasPreferredChanges = preferredName.trim() !== (user?.user_metadata?.preferred_name || '');

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : '';

  const CurrentAvatarIcon = getAvatarIcon(selectedAvatar);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Profile" size="md">
      <div className="account-settings">
        {/* Profile Section */}
        <section className="settings-section">
          <h3 className="settings-section-title">Account</h3>

          <div className="settings-avatar-row">
            <div className="settings-field settings-avatar-field">
              <div className="settings-avatar-header">
                <label className="settings-label">Avatar</label>
                <div className="settings-avatar-current">
                  <CurrentAvatarIcon size={20} />
                </div>
                {savingAvatar && <Loader2 size={14} className="spinning" />}
              </div>
            </div>
            <div className="settings-field settings-preferred-field">
              <label className="settings-label">What should Cowork call you?</label>
              <div className="settings-input-row">
                <input
                  type="text"
                  className="settings-input"
                  value={preferredName}
                  onChange={(e) => setPreferredName(e.target.value)}
                  placeholder="e.g. Joe, Laura"
                />
                <button
                  className="settings-save-btn"
                  onClick={handleSavePreferredName}
                  disabled={savingPreferred || !hasPreferredChanges}
                >
                  {savingPreferred ? <Loader2 size={14} className="spinning" /> : savedPreferred ? <Check size={14} /> : 'Save'}
                </button>
              </div>
            </div>
          </div>

          <div className="settings-field">
            <div className="settings-avatar-grid">
              {AVATAR_ICONS.map((avatar) => {
                const Icon = avatar.icon;
                return (
                  <button
                    key={avatar.id}
                    className={`settings-avatar-option ${avatar.id === selectedAvatar ? 'active' : ''}`}
                    onClick={() => handleSelectAvatar(avatar.id)}
                    title={avatar.label}
                    disabled={savingAvatar}
                  >
                    <Icon size={16} />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="settings-field">
            <label className="settings-label">Display Name</label>
            <div className="settings-input-row">
              <input
                type="text"
                className="settings-input"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your display name"
              />
              <button
                className="settings-save-btn"
                onClick={handleSaveProfile}
                disabled={saving || !hasChanges}
              >
                {saving ? <Loader2 size={14} className="spinning" /> : saved ? <Check size={14} /> : 'Save'}
              </button>
            </div>
            {error && <p className="settings-error">{error}</p>}
          </div>

          <div className="settings-field">
            <label className="settings-label">Email</label>
            <p className="settings-value">{user?.email}</p>
          </div>

          <div className="settings-field">
            <label className="settings-label">Member Since</label>
            <p className="settings-value">{memberSince}</p>
          </div>
        </section>
      </div>
    </Modal>
  );
}
