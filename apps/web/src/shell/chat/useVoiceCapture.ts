import { useEffect, useRef, useState } from 'react'

const BAR_COUNT = 48
const MIN_SCALE = 0.08

export function useVoiceCapture() {
  const [active, setActive] = useState(false)
  const [error, setError] = useState('')
  const waveformRef = useRef<HTMLDivElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const contextRef = useRef<AudioContext | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const frameRef = useRef<number | null>(null)
  const lastPaintRef = useRef(0)

  function paint(levels: number[]) {
    const bars = waveformRef.current?.children
    if (!bars) return
    for (let index = 0; index < bars.length; index++) {
      const element = bars[index] as HTMLElement
      element.style.transform = `scaleY(${levels[index] ?? MIN_SCALE})`
    }
  }

  function releaseHardware() {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    frameRef.current = null
    try { sourceRef.current?.disconnect() } catch { /* already disconnected */ }
    sourceRef.current = null
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    const context = contextRef.current
    contextRef.current = null
    if (context && context.state !== 'closed') void context.close()
  }

  function stop() {
    releaseHardware()
    setActive(false)
    paint(Array.from({ length: BAR_COUNT }, () => MIN_SCALE))
  }

  async function start() {
    setError('')
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Микрофон недоступен в этом браузере.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      const extendedWindow = window as Window & { webkitAudioContext?: typeof AudioContext }
      const AudioContextCtor = window.AudioContext ?? extendedWindow.webkitAudioContext
      if (!AudioContextCtor) throw new Error('AudioContext unavailable')
      const context = new AudioContextCtor()
      if (context.state === 'suspended') await context.resume()
      const analyser = context.createAnalyser()
      analyser.fftSize = 128
      analyser.smoothingTimeConstant = 0.76
      const source = context.createMediaStreamSource(stream)
      source.connect(analyser)
      streamRef.current = stream
      contextRef.current = context
      sourceRef.current = source
      for (const track of stream.getTracks()) track.addEventListener('ended', stop, { once: true })
      setActive(true)
      lastPaintRef.current = 0
      const bins = new Uint8Array(analyser.frequencyBinCount)
      const tick = (time: number) => {
        analyser.getByteFrequencyData(bins)
        if (time - lastPaintRef.current > 42) {
          lastPaintRef.current = time
          const step = Math.max(1, Math.floor(bins.length / BAR_COUNT))
          const levels = Array.from({ length: BAR_COUNT }, (_, index) => {
            const start = Math.min(index * step, bins.length - 1)
            const end = Math.min(start + step, bins.length)
            let total = 0
            for (let offset = start; offset < end; offset++) total += bins[offset]
            const level = total / Math.max(1, end - start) / 180
            return Math.max(MIN_SCALE, Math.min(1, level))
          })
          paint(levels)
        }
        frameRef.current = requestAnimationFrame(tick)
      }
      frameRef.current = requestAnimationFrame(tick)
    } catch {
      releaseHardware()
      setActive(false)
      setError('Не удалось получить доступ к микрофону. Проверьте разрешение браузера.')
    }
  }

  useEffect(() => () => releaseHardware(), [])

  return { active, error, waveformRef, start, stop, barCount: BAR_COUNT }
}
