import { Link } from 'react-router-dom'
import { useState } from 'react'
import './Download.css'

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  )
}

function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      type="button"
      className={`copy-btn ${copied ? 'copied' : ''}`}
      onClick={handleCopy}
      title="Copy"
      aria-label={label}
    >
      <CopyIcon />
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

export default function Download() {
  // Use relative URL so it works on any domain
  const wheelUrl = '/downloads/navigator.whl'

  return (
    <div className="download-page">
      <div className="download-content">
        <Link to="/" className="download-back">← Back to Navigator</Link>

        <h1>Download Navigator</h1>

        <section className="download-section">
          <h2>One-line install (recommended)</h2>
          <p>Run this in your terminal:</p>
          <div className="command-block">
            <code>curl -fsSL https://getnavigator.app/install.sh | sh</code>
            <CopyButton
              text="curl -fsSL https://getnavigator.app/install.sh | sh"
              label="Copy install command"
            />
          </div>
        </section>

        <section className="download-section">
          <h2>Install from wheel</h2>
          <p>Download the wheel and install locally:</p>
          <div className="command-block">
            <code>pip install {window.location.origin}{wheelUrl}</code>
            <CopyButton
              text={`pip install ${window.location.origin}${wheelUrl}`}
              label="Copy pip install from URL"
            />
          </div>
          <p className="download-or">
            Or <a href={wheelUrl} download>download navigator.whl</a> and run:
          </p>
          <div className="command-block">
            <code>pip install ~/Downloads/navigator.whl</code>
            <CopyButton text="pip install ~/Downloads/navigator.whl" label="Copy local install command" />
          </div>
        </section>

        <section className="download-section">
          <h2>Install from source</h2>
          <p>For the latest development version:</p>
          <div className="command-block">
            <code>cd navigator && bash install.sh</code>
            <CopyButton text="cd navigator && bash install.sh" label="Copy source install command" />
          </div>
        </section>
      </div>
    </div>
  )
}
