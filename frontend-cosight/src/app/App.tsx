import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { CoSightSidebar } from '../components/layout/CoSightSidebar';
import { OverviewPage } from '../components/dashboard/OverviewPage';
import { WebPage } from '../components/dashboard/WebPage';
import { SeoPage } from '../components/dashboard/SeoPage';
import { EmailPage } from '../components/dashboard/EmailPage';
import { SocialPage } from '../components/dashboard/SocialPage';
import { ReportsPage } from '../components/reports/ReportsPage';
import { ChatPage } from '../components/chat/ChatPage';
import './App.css';

export function App() {
  return (
    <BrowserRouter>
      <div className="cosight-layout">
        <CoSightSidebar />
        <main className="cosight-main">
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/web" element={<WebPage />} />
            <Route path="/seo" element={<SeoPage />} />
            <Route path="/email" element={<EmailPage />} />
            <Route path="/social" element={<SocialPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
