import { useState } from 'react'
import { type CSSProperties } from 'react'
import { HackeryButton } from '../components/hackery-button'
import { launchSRCorporate } from '../store'
import { AlertCircle } from 'lucide-react'

/*
 * Success screen. SR AGENT wordmark stays as the visual anchor
 * (same Collapse Bold treatment as Welcome + the desktop chat intro),
 * with a status line below.
 *
 * Launching the managed console can fail (e.g. the corporate launcher was
 * not materialized in the venv). We catch the Tauri error and surface it
 * inline rather than silently doing nothing.
 */
export default function Success() {
  const [error, setError] = useState<string | null>(null)
  const [launching, setLaunching] = useState(false)

  async function handleLaunch() {
    setError(null)
    setLaunching(true)
    try {
      await launchSRCorporate()
      // On success the installer exits — control never returns here.
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      setLaunching(false)
    }
  }

  return (
    <div className="sr-fade-in flex h-full flex-col items-center justify-center gap-8 px-12 py-10">
      <div className="w-full max-w-2xl min-w-0 text-center">
        <p
          className="fit-text mx-auto mb-4 w-full font-['Collapse'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-midground mix-blend-plus-lighter dark:text-foreground/90"
          style={
            {
              '--fit-text-line-height': '0.9',
              '--fit-text-max': '5rem',
              '--fit-text-min': '2.25rem'
            } as CSSProperties
          }
        >
          <span>
            <span>SR is ready</span>
          </span>
          <span aria-hidden="true">SR is ready</span>
        </p>

        <p className="m-0 text-center text-base leading-normal tracking-tight text-muted-foreground">
          You can launch from here, or any time from the SR shortcut in your Start Menu.
        </p>
      </div>

      <HackeryButton
        disabled={launching}
        label={launching ? 'Launching' : 'Launch'}
        loading={launching}
        onClick={() => void handleLaunch()}
      />

      {error && (
        <div role="alert" className="flex max-w-2xl items-start gap-2 text-sm">
          <AlertCircle size={16} className="mt-0.5 shrink-0 text-destructive" />
          <div className="min-w-0">
            <div className="font-medium text-destructive">Couldn&rsquo;t launch SR</div>
            <div className="mt-0.5 text-muted-foreground">{error}</div>
          </div>
        </div>
      )}
    </div>
  )
}
