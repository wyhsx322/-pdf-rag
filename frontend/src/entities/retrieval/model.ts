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
