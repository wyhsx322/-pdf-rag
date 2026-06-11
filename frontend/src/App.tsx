import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import KnowledgeBases from './pages/KnowledgeBases'
import KnowledgeBaseDetail from './pages/KnowledgeBaseDetail'
import SmartChunking from './pages/SmartChunking'
import HybridSearch from './pages/HybridSearch'
import ChatQA from './pages/ChatQA'
import ThesisProject from './pages/ThesisProject'
import ThesisWorkspace from './pages/ThesisWorkspace'
import { ChatProvider } from './context/ChatContext'

export default function App() {
  return (
    <BrowserRouter>
      <ChatProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<KnowledgeBases />} />
            <Route path="/kb/:id" element={<KnowledgeBaseDetail />} />
            <Route path="/chunking" element={<SmartChunking />} />
            <Route path="/search" element={<HybridSearch />} />
            <Route path="/chat" element={<ChatQA />} />
            <Route path="/thesis" element={<ThesisProject />} />
            <Route path="/thesis/:id" element={<ThesisWorkspace />} />
          </Routes>
        </Layout>
      </ChatProvider>
    </BrowserRouter>
  )
}
