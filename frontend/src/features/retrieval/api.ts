import { api } from '../../shared/api/http'

// ── 混合检索 ──

export interface SearchResultItem {
  rank: number
  chunk_id: string
  text: string
  page: number | null
  source: string
  vector_score: number
  bm25_score: number
  rrf_score: number
  rerank_score: number | null
  is_figure: boolean
  figure_type: string | null
  caption: string | null
  image_file: string | null
  image_path: string | null
}

export interface SearchDiagnostics {
  result_count: number
  unique_sources: number
  figure_results: number
  avg_text_chars: number
  top_source: string | null
  top_source_share: number
  best_vector_score: number
  best_bm25_score: number
  best_rrf_score: number
  score_spread: number
  confidence: 'low' | 'medium' | 'high'
  risks: string[]
  recommendations: string[]
}

export interface SearchResponse {
  query: string
  total_results: number
  search_mode: string
  results: SearchResultItem[]
  elapsed_seconds: number
  diagnostics: SearchDiagnostics
}

export async function hybridSearch(
  kbId: number,
  query: string,
  topK: number = 10,
  useReranker: boolean = false,
  useRewrite: boolean = true,
  useHyde: boolean = false,
): Promise<SearchResponse> {
  const { data } = await api.post('/search', {
    kb_id: kbId,
    query,
    top_k: topK,
    use_reranker: useReranker,
    use_rewrite: useRewrite,
    use_hyde: useHyde,
  })
  return data
}
