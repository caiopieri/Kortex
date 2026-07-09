import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { applyTheme, getStoredTheme, getStoredMode } from './theme.js'
import './index.css'
import App from './App.jsx'

applyTheme(getStoredTheme(), getStoredMode());

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
