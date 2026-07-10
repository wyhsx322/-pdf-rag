import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './layout/Layout'
import Chat from '../pages/chat/Chat'
import KnowledgeBases from '../pages/knowledge-base/KnowledgeBases'
import KnowledgeBaseDetail from '../pages/knowledge-base/KnowledgeBaseDetail'
import Search from '../pages/search/Search'
import Settings from '../pages/settings/Settings'
import ThesisProject from '../pages/writing/ThesisProject'
import ThesisWorkspace from '../pages/writing/ThesisWorkspace'
import SectionWorkspace from '../pages/writing/SectionWorkspace'
import { ChatProvider } from '../features/chat-session/ChatContext'

export default function App() {
  return (
    <BrowserRouter>
      <ChatProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<ThesisProject />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/knowledge" element={<KnowledgeBases />} />
            <Route path="/knowledge/search" element={<Search />} />
            <Route path="/knowledge/:id" element={<KnowledgeBaseDetail />} />
            <Route path="/search" element={<Search />} />
            <Route path="/writing" element={<ThesisProject />} />
            <Route path="/writing/:id" element={<ThesisWorkspace />} />
            <Route path="/writing/:id/section/:sid" element={<SectionWorkspace />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
      </ChatProvider>
    </BrowserRouter>
  )
}
