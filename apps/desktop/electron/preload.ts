import { contextBridge, ipcRenderer, webUtils } from 'electron'

contextBridge.exposeInMainWorld('srDesktop', {
  getConnection: profile => ipcRenderer.invoke('sr:connection', profile),
  revalidateConnection: () => ipcRenderer.invoke('sr:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('sr:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('sr:gateway:ws-url', profile),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('sr:window:openSession', sessionId, opts),
  openNewSessionWindow: () => ipcRenderer.invoke('sr:window:openNewSession'),
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('sr:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('sr:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('sr:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('sr:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('sr:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('sr:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('sr:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sr:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('sr:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sr:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('sr:pet-overlay:control', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('sr:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('sr:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('sr:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('sr:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('sr:connection-config:test', payload),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('sr:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('sr:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('sr:connection-config:oauth-logout', remoteUrl),
  // SR Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('sr:cloud:status'),
    login: () => ipcRenderer.invoke('sr:cloud:login'),
    logout: () => ipcRenderer.invoke('sr:cloud:logout'),
    discover: org => ipcRenderer.invoke('sr:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('sr:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('sr:profile:get'),
    set: name => ipcRenderer.invoke('sr:profile:set', name)
  },
  api: request => ipcRenderer.invoke('sr:api', request),
  notify: payload => ipcRenderer.invoke('sr:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('sr:requestMicrophoneAccess'),
  readFileDataUrl: filePath => ipcRenderer.invoke('sr:readFileDataUrl', filePath),
  readFileText: filePath => ipcRenderer.invoke('sr:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('sr:selectPaths', options),
  writeClipboard: text => ipcRenderer.invoke('sr:writeClipboard', text),
  saveImageFromUrl: url => ipcRenderer.invoke('sr:saveImageFromUrl', url),
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('sr:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('sr:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('sr:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('sr:watchPreviewFile', url),
  stopPreviewFileWatch: id => ipcRenderer.invoke('sr:stopPreviewFileWatch', id),
  setTitleBarTheme: payload => ipcRenderer.send('sr:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('sr:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('sr:translucency', payload),
  setPreviewShortcutActive: active => ipcRenderer.send('sr:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('sr:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('sr:openPreviewInBrowser', url),
  fetchLinkTitle: url => ipcRenderer.invoke('sr:fetchLinkTitle', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('sr:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('sr:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('sr:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('sr:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('sr:zoom:get'),
    setPercent: percent => ipcRenderer.send('sr:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sr:zoom:changed', listener)

      return () => ipcRenderer.removeListener('sr:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('sr:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('sr:logs:recent'),
  readDir: dirPath => ipcRenderer.invoke('sr:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('sr:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('sr:fs:reveal', targetPath),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('sr:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('sr:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('sr:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('sr:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('sr:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('sr:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('sr:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('sr:git:branchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('sr:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('sr:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('sr:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('sr:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('sr:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('sr:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('sr:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('sr:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('sr:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('sr:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('sr:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('sr:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('sr:git:review:shipInfo', repoPath),
      createPr: repoPath => ipcRenderer.invoke('sr:git:review:createPr', repoPath)
    }
  },
  terminal: {
    cwd: id => ipcRenderer.invoke('sr:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('sr:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('sr:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('sr:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('sr:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `sr:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `sr:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sr:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('sr:close-preview-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sr:open-updates', listener)

    return () => ipcRenderer.removeListener('sr:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sr:deep-link', listener)

    return () => ipcRenderer.removeListener('sr:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('sr:deep-link-ready'),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sr:window-state-changed', listener)

    return () => ipcRenderer.removeListener('sr:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('sr:focus-session', listener)

    return () => ipcRenderer.removeListener('sr:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sr:notification-action', listener)

    return () => ipcRenderer.removeListener('sr:notification-action', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sr:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('sr:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sr:backend-exit', listener)

    return () => ipcRenderer.removeListener('sr:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('sr:connection:applied', listener)

    return () => ipcRenderer.removeListener('sr:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('sr:power-resume', listener)

    return () => ipcRenderer.removeListener('sr:power-resume', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sr:boot-progress', listener)

    return () => ipcRenderer.removeListener('sr:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('sr:bootstrap:get'),
  resetBootstrap: () => ipcRenderer.invoke('sr:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('sr:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('sr:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sr:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('sr:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('sr:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('sr:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('sr:uninstall:summary'),
    run: mode => ipcRenderer.invoke('sr:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('sr:updates:check'),
    apply: opts => ipcRenderer.invoke('sr:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('sr:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('sr:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sr:updates:progress', listener)

      return () => ipcRenderer.removeListener('sr:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('sr:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('sr:vscode-theme:search', query)
  }
})
