import { useEffect, useRef, useState } from 'react'
import { Icon } from '../../shared/ui/Icon'

export function UploadBox() {
  const input = useRef<HTMLInputElement>(null)
  const url = useRef('')
  const sequence = useRef(0)
  const [file, setFile] = useState<{ name: string; url: string } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => () => { sequence.current++; URL.revokeObjectURL(url.current) }, [])
  async function choose(value?: File) {
    const request = ++sequence.current
    setError('')
    if (!value) return
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(value.type) || value.size > 8 * 1024 * 1024) {
      setError('Выберите PNG, JPEG или WebP до 8 МБ.'); return
    }
    try {
      const bitmap = await createImageBitmap(value)
      const valid = bitmap.width * bitmap.height <= 32000000
      bitmap.close()
      if (request !== sequence.current) return
      if (!valid) { setError('Для макета выберите изображение до 32 мегапикселей.'); return }
      URL.revokeObjectURL(url.current)
      url.current = URL.createObjectURL(value)
      setFile({ name: value.name, url: url.current })
    } catch { if (request === sequence.current) setError('Этот файл не удалось прочитать как изображение.') }
  }
  return <div className="upload-area">
    <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" hidden aria-label="Выбрать исходное изображение" onChange={e => { void choose(e.target.files?.[0]); e.target.value = '' }} />
    {file ? <div className="reference-preview"><img src={file.url} alt="Локальный исходник" /><span>{file.name}</span><button type="button" className="icon-button" aria-label="Удалить исходник" onClick={() => { sequence.current++; URL.revokeObjectURL(url.current); setFile(null) }}><Icon name="close" /></button></div>
      : <button type="button" className="upload-button" onClick={() => input.current?.click()}><Icon name="plus" /><span>Добавить исходник<small>PNG, JPEG, WebP · до 8 МБ</small></span></button>}
    <small>Только предпросмотр в браузере. Файл не отправляется и не обрабатывается AI.</small>
    {error && <p className="field-error" role="alert">{error}</p>}
  </div>
}
