/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import {
  Download,
  Copy,
  Check,
  Terminal,
  FileCode2,
  Sun,
  Moon,
  Layers,
  Cpu,
  CheckCircle2,
  Sliders,
} from 'lucide-react';
import {
  STANDALONE_PYQT6_APP_SOURCE,
  STANDALONE_REQUIREMENTS_TXT,
  STANDALONE_WINDOWS_BATCH_LAUNCHER,
} from './engine/purePythonAppGenerator';

export default function App() {
  const [darkMode, setDarkMode] = useState(true);
  const [activeFileTab, setActiveFileTab] = useState<'python' | 'batch' | 'requirements'>('python');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [darkMode]);

  const currentCode =
    activeFileTab === 'python'
      ? STANDALONE_PYQT6_APP_SOURCE
      : activeFileTab === 'batch'
      ? STANDALONE_WINDOWS_BATCH_LAUNCHER
      : STANDALONE_REQUIREMENTS_TXT;

  const triggerDownload = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(currentCode);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#F5F7FA] dark:bg-[#0D1117] text-slate-900 dark:text-slate-100">
      {/* Strict 3-Zone Top Bar Contract */}
      <header className="sticky top-0 z-30 bg-white/95 dark:bg-[#161C26]/95 backdrop-blur border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-[1320px] mx-auto flex items-center justify-between gap-8 px-6 py-4">
          {/* Zone 1: Brand Wordmark */}
          <a
            href="#package"
            className="text-lg font-bold tracking-tight text-slate-900 dark:text-white whitespace-nowrap shrink-0 font-display"
          >
            LegionDeck PyQt6
          </a>

          {/* Zone 2: Concise Single-Line Links */}
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600 dark:text-slate-300">
            <a
              href="#package"
              className="hover:text-[#0D84FF] transition-colors whitespace-nowrap shrink-0"
            >
              Standalone App
            </a>
            <a
              href="#features"
              className="hover:text-[#0D84FF] transition-colors whitespace-nowrap shrink-0"
            >
              PyQt6 Features
            </a>
            <a
              href="#setup"
              className="hover:text-[#0D84FF] transition-colors whitespace-nowrap shrink-0"
            >
              Windows Setup
            </a>
            <a
              href="#source"
              className="hover:text-[#0D84FF] transition-colors whitespace-nowrap shrink-0"
            >
              Python Source
            </a>
          </nav>

          {/* Zone 3: 1 Primary Action Button */}
          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={() =>
                triggerDownload('legion_go_steamdeck_app.py', STANDALONE_PYQT6_APP_SOURCE)
              }
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-[#0D84FF] hover:bg-[#006EE6] rounded-xl transition-colors whitespace-nowrap shrink-0"
            >
              <Download className="w-3.5 h-3.5" />
              Download legion_go_steamdeck_app.py
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1320px] mx-auto px-6 py-8 space-y-8">
        {/* Hero / Direct Standalone Package Card */}
        <section
          id="package"
          className="bg-white dark:bg-[#161C26] border border-slate-200 dark:border-slate-800 rounded-2xl p-6"
        >
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mb-2">
                <span>100% Standalone PyQt6 Desktop App</span>
                <span aria-hidden="true">·</span>
                <span>Zero Browser or WebUI Needed</span>
                <span aria-hidden="true">·</span>
                <span>Auto-Saves to legion_deck_profile.json</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white text-balance">
                Standalone PyQt6 Lenovo Legion Go to Steam Deck Controller Studio
              </h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">
                All interactive controller testing, 2D <code className="font-mono">QPainter</code>{' '}
                trackpad &amp; gyro visualizers, button remapping dropdowns (<code className="font-mono">Y1–Y3</code>,{' '}
                <code className="font-mono">M2–M3</code>, united <code className="font-mono">RB / M1</code>,{' '}
                <code className="font-mono">Legion L/R</code>, device-isolated{' '}
                <code className="font-mono">VID_17EF Scroll Wheel Up/Down/Click</code>), manual{' '}
                <code className="font-mono">LT / RT Analog &amp; Half-Press Stage Calibration</code>,
                JSON profile auto-saving, system tray background runner, and the 250Hz Windows{' '}
                <code className="font-mono">USB/IP</code> (<code className="font-mono">0x28DE:0x1205</code>) +{' '}
                <code className="font-mono">HidHide</code> bridge are packed inside{' '}
                <code className="font-mono">legion_go_steamdeck_app.py</code>.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5 shrink-0">
              <button
                type="button"
                onClick={() =>
                  triggerDownload('legion_go_steamdeck_app.py', STANDALONE_PYQT6_APP_SOURCE)
                }
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#0D84FF] hover:bg-[#006EE6] text-white transition-colors whitespace-nowrap shrink-0"
              >
                <Download className="w-4 h-4" />
                Download legion_go_steamdeck_app.py
              </button>

              <button
                type="button"
                onClick={() =>
                  triggerDownload('run_windows_admin.bat', STANDALONE_WINDOWS_BATCH_LAUNCHER)
                }
                className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-xs font-medium bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition-colors whitespace-nowrap shrink-0"
              >
                <Terminal className="w-4 h-4" />
                Download run_windows_admin.bat
              </button>

              <button
                type="button"
                onClick={() => setDarkMode((d) => !d)}
                className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-slate-100 dark:bg-[#0D1117] border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 hover:border-[#0D84FF] transition-colors whitespace-nowrap shrink-0"
              >
                {darkMode ? (
                  <>
                    <Sun className="w-3.5 h-3.5 text-amber-400" />
                    Light
                  </>
                ) : (
                  <>
                    <Moon className="w-3.5 h-3.5 text-slate-700" />
                    Dark
                  </>
                )}
              </button>
            </div>
          </div>

          {/* 4-Column Built-In PyQt6 Feature Summary */}
          <div
            id="features"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-200 dark:border-slate-800"
          >
            <div className="flex items-start gap-3">
              <span className="mtz-icon-box w-9 h-9 bg-blue-500/15 text-[#0D84FF]">
                <Layers className="w-4 h-4" />
              </span>
              <div>
                <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                  Built-In PyQt6 Hardware Tester
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Interactive 2D QPainter Trackpad, Gyro &amp; Button Canvas inside the desktop app
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <span className="mtz-icon-box w-9 h-9 bg-cyan-500/15 text-cyan-600 dark:text-cyan-400">
                <Sliders className="w-4 h-4" />
              </span>
              <div>
                <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                  Auto-Save JSON + 3 Presets
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Automatically saves every binding change to legion_deck_profile.json
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <span className="mtz-icon-box w-9 h-9 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                <Cpu className="w-4 h-4" />
              </span>
              <div>
                <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                  System Tray &amp; Auto-Start
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Minimizes to QSystemTrayIcon with MIUI squircle icon &amp; launch auto-start
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <span className="mtz-icon-box w-9 h-9 bg-amber-500/15 text-amber-600 dark:text-amber-400">
                <CheckCircle2 className="w-4 h-4" />
              </span>
              <div>
                <div className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                  64-Byte Neptune + HidHide
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Answers 0x81/0x83/0x87/0xAE Feature Reports &amp; cloaks VID_17EF double-input
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3-Step Windows Run Instructions */}
        <section id="setup" className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-[#161C26] border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-2">
              <span className="mtz-icon-box w-8 h-8 bg-[#0D84FF]/15 text-[#0D84FF] font-mono text-xs font-bold">
                01
              </span>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Install PyQt6 &amp; hidapi
              </h2>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Run <code className="font-mono">pip install PyQt6 hidapi</code> (or double-click{' '}
              <code className="font-mono">run_windows_admin.bat</code>) alongside the WHQL-signed{' '}
              <code className="font-mono">usbip-win2</code> driver on your Lenovo Legion Go.
            </p>
          </div>

          <div className="bg-white dark:bg-[#161C26] border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-2">
              <span className="mtz-icon-box w-8 h-8 bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 font-mono text-xs font-bold">
                02
              </span>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Configure &amp; Test in PyQt6 Window
              </h2>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Use <strong>Tab 1 (Interactive Tester &amp; Visual Canvas)</strong> and{' '}
              <strong>Tab 2 (Remapper)</strong> inside the native Python window to test and rebind{' '}
              <code className="font-mono">Y1–Y3</code>, <code className="font-mono">M1–M3</code>,{' '}
              <code className="font-mono">Trackpad</code>, and <code className="font-mono">Gyro</code>.
            </p>
          </div>

          <div className="bg-white dark:bg-[#161C26] border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-2">
              <span className="mtz-icon-box w-8 h-8 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-mono text-xs font-bold">
                03
              </span>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Start Emulation &amp; Minimize to Tray
              </h2>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Click <strong>Start Steam Deck Emulation</strong> in the PyQt6 header (or enable{' '}
              <em>Auto-Start on Launch</em>). Windows Steam immediately detects a physical{' '}
              <strong>Steam Deck Controller (`0x28DE:0x1205`)</strong>.
            </p>
          </div>
        </section>

        {/* Complete Standalone PyQt6 Source Code Viewer */}
        <section
          id="source"
          className="bg-white dark:bg-[#161C26] border border-slate-200 dark:border-slate-800 rounded-2xl p-6"
        >
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 mb-4 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <span className="mtz-icon-box w-10 h-10 bg-blue-500/15 text-[#0D84FF]">
                <FileCode2 className="w-5 h-5" />
              </span>
              <div>
                <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                  Standalone PyQt6 Application Files
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Also saved directly in the project root as /legion_go_steamdeck_app.py,
                  /run_windows_admin.bat, and /requirements.txt
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-[#0D1117] rounded-xl border border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setActiveFileTab('python')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors whitespace-nowrap ${
                    activeFileTab === 'python'
                      ? 'bg-[#0D84FF] text-white'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  legion_go_steamdeck_app.py
                </button>
                <button
                  type="button"
                  onClick={() => setActiveFileTab('batch')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors whitespace-nowrap ${
                    activeFileTab === 'batch'
                      ? 'bg-[#0D84FF] text-white'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  run_windows_admin.bat
                </button>
                <button
                  type="button"
                  onClick={() => setActiveFileTab('requirements')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors whitespace-nowrap ${
                    activeFileTab === 'requirements'
                      ? 'bg-[#0D84FF] text-white'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  requirements.txt
                </button>
              </div>

              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-500" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    Copy File
                  </>
                )}
              </button>
            </div>
          </div>

          <pre className="p-4 rounded-xl bg-[#0B0F17] text-slate-200 text-xs font-mono overflow-x-auto max-h-[600px] leading-relaxed border border-slate-800">
            <code>{currentCode}</code>
          </pre>
        </section>
      </main>
    </div>
  );
}
