import React from 'react';
import ReactDOM from 'react-dom/client';
import '../model.js';
import '../presentation.js';
import '../sample.js';
import App from './App.jsx';
import './style.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode><App /></React.StrictMode>,
);
