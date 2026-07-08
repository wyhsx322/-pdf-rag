import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Chat from './pages/Chat'
import KnowledgeBases from './pages/KnowledgeBases'
import KnowledgeBaseDetail from './pages/KnowledgeBaseDetail'
import Search from './pages/Search'
import Settings from './pages/Settings'
import ThesisProject from './pages/ThesisProject'
import ThesisWorkspace from './pages/ThesisWorkspace'
import SectionWorkspace from './pages/SectionWorkspace'
import { ChatProvider } from './context/ChatContext'

export default function App() {
  return (
    <BrowserRouter>
      <ChatProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Chat />} />
            <Route path="/knowledge" element={<KnowledgeBases />} />
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
