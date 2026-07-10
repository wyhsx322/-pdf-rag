import { api } from '../../shared/api/http'

// ── 模型 / API Key 配置 ──

export interface KeyState {
  configured: boolean
  hint: string // 掩码提示，如 "••••3a7f"
}

export interface ModelRole {
  model: string
  base_url?: string
  api_key_env?: string
}

export interface ModelOption {
  id: string
  label: string
  model: string
  base_url: string
  api_key_env: string
  provider: string
}

export interface SettingsResponse {
  keys: Record<string, KeyState>
  models: Record<string, ModelRole>
  model_options: ModelOption[]
}

export interface SettingsUpdate {
  keys?: Record<string, string> // 仅传需更新的明文 Key
  models?: Record<string, ModelRole>
}

export async function getSettings(): Promise<SettingsResponse> {
  const { data } = await api.get('/settings')
  return data
}

export async function updateSettings(payload: SettingsUpdate): Promise<SettingsResponse> {
  const { data } = await api.put('/settings', payload)
  return data
}

export async function testProvider(provider: string): Promise<{ ok: boolean; message: string }> {
  const { data } = await api.post('/settings/test', { provider })
  return data
}
