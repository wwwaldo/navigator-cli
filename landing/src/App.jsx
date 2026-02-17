import { useState } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Docs from './Docs'
import Download from './Download'
import './App.css'

function NavigatorLogo() {
  return (
    <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="16" cy="16" r="10" />
      <path d="M16 6v4M16 22v4M6 16h4M22 16h4" />
      <path d="M10.34 10.34l2.83 2.83M18.83 18.83l2.83 2.83M10.34 21.66l2.83-2.83M18.83 13.17l2.83-2.83" />
    </svg>
  )
}

function NavigatorMascot() {
  return (
    <svg viewBox="0 0 120 120" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {/* Compass body - friendly circular character */}
      <circle cx="60" cy="60" r="38" />
      {/* Compass cross / cardinal points */}
      <path d="M60 22v6M60 92v6M22 60h6M92 60h6" />
      <path d="M32 32l4.24 4.24M83.76 83.76L88 88M32 88l4.24-4.24M83.76 36.24L88 32" />
      {/* Needle */}
      <path d="M60 60l18-18" strokeWidth="2.5" />
      <path d="M60 60l-14 14" strokeWidth="1.5" opacity="0.6" />
      {/* Center dot */}
      <circle cx="60" cy="60" r="4" fill="currentColor" />
      {/* Waving arm - Ollama-style */}
      <path d="M98 38c2 2 4 6 2 10s-6 4-8 2" strokeWidth="2" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  )
}

const INSTALL_CMD = 'curl -fsSL https://getnavigator.app/install.sh | sh'

function App() {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(INSTALL_CMD)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback for older browsers
      const textarea = document.createElement('textarea')
      textarea.value = INSTALL_CMD
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <BrowserRouter>
      <header className="header">
        <div className="header-left">
          <Link to="/" className="header-logo">
            <NavigatorLogo />
            <span style={{ fontWeight: 600, fontSize: '1rem' }}>Navigator</span>
          </Link>
          <nav className="header-nav">
            <a href="#features">Features</a>
            <Link to="/docs">Docs</Link>
            <a href="#github">GitHub</a>
          </nav>
        </div>
        <div className="header-search">
          <input type="search" placeholder="Search Navigator" aria-label="Search" />
        </div>
        <div className="header-right">
          <button type="button" className="btn-signin">Sign in</button>
          <Link to="/download" className="btn-download" style={{ textDecoration: 'none', display: 'inline-block' }}>Download</Link>
        </div>
      </header>

      <Routes>
        <Route
          path="/"
          element={
            <main className="splash">
              <div className="splash-mascot">
                <NavigatorMascot />
              </div>
              <h1>Teach AI from your own data</h1>
              <div className="splash-command">
                <code>{INSTALL_CMD}</code>
                <button
                  type="button"
                  className={`splash-command-copy ${copied ? 'splash-command-copied' : ''}`}
                  onClick={handleCopy}
                  title="Copy to clipboard"
                  aria-label="Copy command"
                >
                  <CopyIcon />
                </button>
              </div>
              <p className="splash-subtext">
                paste this in terminal, or <Link to="/download">download Navigator</Link>
              </p>
            </main>
          }
        />
        <Route path="/docs" element={<Docs />} />
        <Route path="/download" element={<Download />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
