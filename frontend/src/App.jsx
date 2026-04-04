import { Navigate, Route, Routes } from 'react-router-dom'

import AppShell from './components/AppShell'
import BackupPage from './pages/BackupPage'
import BulkUploadPage from './pages/BulkUploadPage'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import FavoritesPage from './pages/FavoritesPage'
import NewDocumentPage from './pages/NewDocumentPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/backup" element={<BackupPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/new" element={<NewDocumentPage />} />
        <Route path="/documents/bulk" element={<BulkUploadPage />} />
      </Route>
    </Routes>
  )
}
