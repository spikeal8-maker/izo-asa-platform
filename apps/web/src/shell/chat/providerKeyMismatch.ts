export type CredentialProvider = 'deepseek' | 'openrouter'

/** An unambiguous cross-provider prefix is a hard error, not failed verification. */
export function providerKeyMismatch(provider: CredentialProvider, key: string): string | null {
  const value = key.trim()
  if (provider === 'deepseek' && /^sk-or-/i.test(value)) {
    return 'Это ключ OpenRouter. Вставьте его в раздел OpenRouter, а не DeepSeek.'
  }
  if (provider === 'openrouter' && /^sk-[a-f0-9]{32}$/i.test(value)) {
    return 'Это ключ формата DeepSeek. Вставьте его в раздел DeepSeek, а не OpenRouter.'
  }
  return null
}
