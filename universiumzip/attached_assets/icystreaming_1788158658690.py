#!/usr/bin/env python3
"""
IcyStreaming - Netflix‑style streaming app with live search, darker themes.
Uses TMDB for metadata and videasy.to for playback.
"""

import os
import json
from flask import Flask, render_template_string, request, jsonify
import requests

app = Flask(__name__)

TMDB_API_KEY = "3aed9cd7abb1ae110e6c564c9cedd32f"
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"
TMDB_THUMB = "https://image.tmdb.org/t/p/w92"

# ----------------------------------------------------------------------
# HTML template (all CSS/JS inlined)
# ----------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IcyStreaming</title>
    <style>
        /* ---------- CSS Variables & Darker Themes ---------- */
        :root {
            --bg: #07131f;
            --bg-secondary: #0b1a2a;
            --bg-card: #132433;
            --text: #e8f0f8;
            --text-muted: #7a9bb5;
            --accent: #4fc3f7;
            --accent-hover: #81d4fa;
            --shadow: rgba(0,10,20,0.7);
            --border-light: rgba(255,255,255,0.06);
            --gradient-start: #07131f;
            --gradient-end: #0b2a3a;
        }
        body.icy {
            --bg: #07131f;
            --bg-secondary: #0b1a2a;
            --bg-card: #132433;
            --text: #e8f0f8;
            --text-muted: #7a9bb5;
            --accent: #4fc3f7;
            --accent-hover: #81d4fa;
            --shadow: rgba(0,10,20,0.7);
            --border-light: rgba(255,255,255,0.06);
            --gradient-start: #07131f;
            --gradient-end: #0b2a3a;
        }
        body.ocean {
            --bg: #001220;
            --bg-secondary: #002435;
            --bg-card: #003850;
            --text: #d6edf5;
            --text-muted: #6fa3b9;
            --accent: #00bcd4;
            --accent-hover: #26c6da;
            --shadow: rgba(0,20,40,0.8);
            --border-light: rgba(255,255,255,0.08);
            --gradient-start: #001220;
            --gradient-end: #004a60;
        }
        body.dark {
            --bg: #0a0a0a;
            --bg-secondary: #141414;
            --bg-card: #1e1e1e;
            --text: #e5e5e5;
            --text-muted: #999;
            --accent: #e50914;
            --accent-hover: #f40612;
            --shadow: rgba(0,0,0,0.9);
            --border-light: rgba(255,255,255,0.05);
            --gradient-start: #0a0a0a;
            --gradient-end: #1a1a1a;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Segoe UI', Roboto, Arial, sans-serif;
            overflow-x: hidden;
            transition: background 0.4s ease, color 0.3s ease;
        }
        a { color: var(--text); text-decoration: none; }
        button { cursor: pointer; border: none; background: none; color: inherit; font: inherit; }

        /* ---------- Scrollbar ---------- */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-secondary); }
        ::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 4px; }

        /* ---------- Navbar ---------- */
        .navbar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 100;
            padding: 16px 40px;
            display: flex;
            align-items: center;
            background: linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, transparent 100%);
            transition: background 0.3s ease, box-shadow 0.3s;
            height: 70px;
        }
        .navbar.scrolled {
            background: var(--bg-secondary);
            box-shadow: 0 2px 20px var(--shadow);
        }
        .logo {
            font-size: 26px;
            font-weight: 700;
            color: var(--accent);
            margin-right: 40px;
            letter-spacing: -0.5px;
            text-shadow: 0 0 20px rgba(79,195,247,0.2);
        }
        .nav-links { display: flex; gap: 20px; font-size: 14px; }
        .nav-links a {
            padding: 6px 0;
            border-bottom: 2px solid transparent;
            transition: border 0.2s, color 0.2s;
            color: var(--text-muted);
        }
        .nav-links a:hover, .nav-links a.active {
            color: var(--text);
            border-bottom-color: var(--accent);
        }
        .nav-right {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 16px;
            position: relative;
        }
        .search-container {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(255,255,255,0.06);
            padding: 6px 14px;
            border-radius: 24px;
            transition: background 0.3s, box-shadow 0.3s;
            border: 1px solid transparent;
        }
        .search-container:focus-within {
            background: rgba(255,255,255,0.12);
            border-color: var(--accent);
            box-shadow: 0 0 20px rgba(79,195,247,0.1);
        }
        .search-container input {
            background: transparent;
            border: none;
            color: var(--text);
            font-size: 14px;
            width: 180px;
            outline: none;
        }
        .search-container input::placeholder { color: var(--text-muted); }
        .search-container button {
            background: var(--accent);
            color: var(--bg);
            padding: 4px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 13px;
            transition: background 0.3s, transform 0.1s;
        }
        .search-container button:hover { background: var(--accent-hover); }
        .search-container button:active { transform: scale(0.96); }

        /* ---------- Search Suggestions ---------- */
        .suggestions {
            position: absolute;
            top: calc(100% + 8px);
            right: 0;
            left: 0;
            background: var(--bg-secondary);
            border: 1px solid var(--border-light);
            border-radius: 12px;
            box-shadow: 0 12px 40px var(--shadow);
            max-height: 400px;
            overflow-y: auto;
            display: none;
            z-index: 200;
            padding: 6px 0;
        }
        .suggestions.active { display: block; }
        .suggestion-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 16px;
            cursor: pointer;
            transition: background 0.2s;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        .suggestion-item:hover {
            background: var(--bg-card);
        }
        .suggestion-item img {
            width: 40px;
            height: 60px;
            object-fit: cover;
            border-radius: 6px;
            background: var(--bg-card);
        }
        .suggestion-item .info {
            flex: 1;
        }
        .suggestion-item .title {
            font-weight: 500;
            font-size: 14px;
        }
        .suggestion-item .sub {
            font-size: 12px;
            color: var(--text-muted);
        }
        .suggestion-item .badge-sm {
            background: rgba(79,195,247,0.15);
            color: var(--accent);
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 11px;
            text-transform: uppercase;
        }

        .settings-btn {
            background: none;
            border: 1px solid var(--text-muted);
            border-radius: 50%;
            width: 36px;
            height: 36px;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: 0.3s;
            color: var(--text-muted);
        }
        .settings-btn:hover {
            border-color: var(--accent);
            color: var(--accent);
            transform: rotate(60deg);
        }

        /* ---------- Main content ---------- */
        #mainContent {
            padding-top: 80px;
            min-height: 100vh;
        }

        /* ---------- Hero ---------- */
        .hero {
            height: 75vh;
            min-height: 400px;
            display: flex;
            align-items: flex-end;
            padding: 0 60px 80px;
            background-size: cover;
            background-position: center top;
            position: relative;
            margin-bottom: -30px;
        }
        .hero::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, var(--bg) 10%, transparent 70%);
        }
        .hero-content {
            position: relative;
            z-index: 2;
            max-width: 600px;
            animation: fadeUp 0.8s ease;
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .hero-title {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 12px;
            text-shadow: 0 2px 20px rgba(0,0,0,0.8);
        }
        .hero-meta {
            display: flex;
            gap: 20px;
            font-size: 14px;
            color: var(--text-muted);
            margin-bottom: 16px;
        }
        .hero-overview {
            font-size: 16px;
            line-height: 1.6;
            opacity: 0.9;
            margin-bottom: 20px;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-shadow: 0 1px 10px rgba(0,0,0,0.5);
        }
        .hero-btn {
            background: var(--accent);
            color: var(--bg);
            padding: 12px 36px;
            border-radius: 30px;
            font-weight: 700;
            font-size: 18px;
            transition: background 0.3s, transform 0.1s;
            box-shadow: 0 4px 30px rgba(79,195,247,0.3);
        }
        .hero-btn:hover { background: var(--accent-hover); }
        .hero-btn:active { transform: scale(0.96); }

        /* ---------- Rows ---------- */
        .row {
            padding: 20px 40px;
        }
        .row-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 12px;
        }
        .row-title {
            font-size: 22px;
            font-weight: 600;
        }
        .row-title a {
            color: var(--text-muted);
            font-size: 14px;
            font-weight: 400;
            margin-left: 12px;
        }
        .row-title a:hover { color: var(--text); }

        .movie-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 20px;
        }

        /* ---------- Cards ---------- */
        .movie-card {
            background: var(--bg-card);
            border-radius: 10px;
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            cursor: pointer;
            position: relative;
            border: 1px solid var(--border-light);
        }
        .movie-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 12px 40px var(--shadow);
            z-index: 5;
        }
        .movie-card img {
            width: 100%;
            aspect-ratio: 2/3;
            object-fit: cover;
            display: block;
            background: var(--bg-secondary);
        }
        .movie-card-info {
            padding: 10px 12px 12px;
        }
        .movie-card-title {
            font-size: 14px;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .movie-card-year {
            font-size: 12px;
            color: var(--text-muted);
        }
        .movie-card .badge {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(4px);
            padding: 2px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--accent);
            border: 1px solid rgba(79,195,247,0.2);
        }
        .loading-card {
            background: var(--bg-card);
            border-radius: 10px;
            aspect-ratio: 2/3;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }

        /* ---------- Modal ---------- */
        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.85);
            backdrop-filter: blur(6px);
            z-index: 200;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .modal-overlay.active { display: flex; }

        .modal {
            background: var(--bg-secondary);
            max-width: 1000px;
            width: 100%;
            max-height: 90vh;
            border-radius: 16px;
            overflow-y: auto;
            position: relative;
            animation: modalIn 0.3s ease;
            border: 1px solid var(--border-light);
        }
        @keyframes modalIn {
            from { opacity: 0; transform: scale(0.95) translateY(20px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }

        .modal-close {
            position: sticky;
            top: 12px;
            right: 20px;
            float: right;
            background: rgba(0,0,0,0.5);
            border: none;
            color: #fff;
            font-size: 28px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            transition: background 0.3s;
            z-index: 10;
        }
        .modal-close:hover { background: var(--accent); color: var(--bg); }

        .modal-body {
            display: flex;
            flex-direction: column;
            padding: 30px;
        }
        .modal-top {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }
        .modal-poster {
            flex: 0 0 200px;
        }
        .modal-poster img {
            width: 100%;
            border-radius: 10px;
            box-shadow: 0 8px 30px var(--shadow);
        }
        .modal-details {
            flex: 1;
            min-width: 250px;
        }
        .modal-title {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .modal-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 12px 24px;
            font-size: 14px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }
        .modal-overview {
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 16px;
        }
        .modal-cast {
            font-size: 14px;
            color: var(--text-muted);
            margin-bottom: 16px;
        }
        .modal-genres {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }
        .modal-genres span {
            background: rgba(255,255,255,0.08);
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            border: 1px solid var(--border-light);
        }

        .watch-section {
            margin-top: 20px;
            border-top: 1px solid var(--border-light);
            padding-top: 20px;
        }
        .watch-btn {
            background: var(--accent);
            color: var(--bg);
            padding: 10px 40px;
            border-radius: 30px;
            font-size: 18px;
            font-weight: 700;
            transition: background 0.3s, transform 0.1s;
            box-shadow: 0 4px 20px rgba(79,195,247,0.3);
        }
        .watch-btn:hover { background: var(--accent-hover); }
        .watch-btn:active { transform: scale(0.96); }

        .tv-selectors {
            display: flex;
            gap: 20px;
            align-items: center;
            margin: 12px 0;
            flex-wrap: wrap;
        }
        .tv-selectors label {
            font-size: 14px;
            color: var(--text-muted);
        }
        .tv-selectors select {
            background: var(--bg-card);
            color: var(--text);
            border: 1px solid var(--border-light);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 14px;
            outline: none;
        }
        .tv-selectors select:focus { border-color: var(--accent); }

        .favorite-btn {
            background: none;
            border: 2px solid var(--text-muted);
            color: var(--text-muted);
            padding: 6px 20px;
            border-radius: 24px;
            font-size: 14px;
            transition: all 0.3s;
            margin-left: 12px;
        }
        .favorite-btn.active {
            border-color: var(--accent);
            color: var(--accent);
        }
        .favorite-btn:hover { opacity: 0.8; }

        /* ---------- Settings Modal ---------- */
        .settings-modal .modal-body {
            padding: 30px 40px;
            max-width: 500px;
            margin: 0 auto;
        }
        .settings-modal .modal-title {
            text-align: center;
            margin-bottom: 20px;
        }
        .theme-options {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        .theme-option {
            background: var(--bg-card);
            border: 2px solid var(--border-light);
            border-radius: 12px;
            padding: 16px 24px;
            text-align: center;
            cursor: pointer;
            transition: 0.3s;
            flex: 1;
            min-width: 100px;
        }
        .theme-option:hover {
            border-color: var(--accent);
            transform: scale(1.05);
        }
        .theme-option.selected {
            border-color: var(--accent);
            box-shadow: 0 0 30px rgba(79,195,247,0.2);
        }
        .theme-option .icon {
            font-size: 36px;
            display: block;
            margin-bottom: 8px;
        }
        .theme-option .name {
            font-weight: 600;
            font-size: 14px;
        }

        /* ---------- Responsive ---------- */
        @media (max-width: 768px) {
            .navbar { padding: 12px 20px; flex-wrap: wrap; height: auto; }
            .logo { margin-right: 20px; font-size: 22px; }
            .nav-links { order: 3; width: 100%; margin-top: 8px; justify-content: center; }
            .nav-right { margin-left: auto; }
            .search-container { width: 100%; }
            .search-container input { width: 100%; }
            .suggestions { left: 0; right: 0; }
            .hero { padding: 0 20px 60px; min-height: 300px; height: 60vh; }
            .hero-title { font-size: 28px; }
            .row { padding: 10px 20px; }
            .movie-grid { grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); }
            .modal-top { flex-direction: column; align-items: center; }
            .modal-poster { flex: 0 0 auto; width: 160px; }
            #mainContent { padding-top: 100px; }
        }
        @media (max-width: 480px) {
            .movie-grid { grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); }
            .hero-title { font-size: 22px; }
            .hero-overview { font-size: 14px; }
        }

        .hidden { display: none !important; }
        .text-center { text-align: center; }
        .mt-2 { margin-top: 20px; }
        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
            font-size: 18px;
        }
    </style>
</head>
<body class="icy">
    <!-- Navbar -->
    <nav class="navbar" id="navbar">
        <div class="logo">❄️ IcyStreaming</div>
        <div class="nav-links">
            <a href="#" class="active" data-section="home">Home</a>
            <a href="#" data-section="search">Search</a>
            <a href="#" data-section="favorites">Favorites</a>
        </div>
        <div class="nav-right">
            <div class="search-container">
                <input type="text" id="searchInput" placeholder="Search movies, TV..." autocomplete="off">
                <button id="searchBtn">Search</button>
                <!-- Suggestions dropdown -->
                <div class="suggestions" id="suggestions"></div>
            </div>
            <button class="settings-btn" id="settingsBtn" title="Settings">⚙️</button>
        </div>
    </nav>

    <!-- Main Content -->
    <main id="mainContent">
        <!-- Home -->
        <section id="homeSection">
            <div id="heroContainer"></div>
            <div id="rowsContainer"></div>
        </section>

        <!-- Search Results -->
        <section id="searchSection" class="hidden">
            <div class="row">
                <div class="row-header">
                    <h2 class="row-title" id="searchResultTitle">Search Results</h2>
                </div>
                <div id="searchGrid" class="movie-grid"></div>
            </div>
        </section>

        <!-- Favorites -->
        <section id="favoritesSection" class="hidden">
            <div class="row">
                <div class="row-header">
                    <h2 class="row-title">⭐ My Favorites</h2>
                </div>
                <div id="favoritesGrid" class="movie-grid"></div>
            </div>
        </section>
    </main>

    <!-- Detail Modal -->
    <div class="modal-overlay" id="modalOverlay">
        <div class="modal">
            <button class="modal-close" id="modalClose">&times;</button>
            <div class="modal-body" id="modalBody">
                <!-- Dynamic content -->
            </div>
        </div>
    </div>

    <!-- Settings Modal -->
    <div class="modal-overlay" id="settingsOverlay">
        <div class="modal settings-modal">
            <button class="modal-close" id="settingsClose">&times;</button>
            <div class="modal-body">
                <h2 class="modal-title">🎨 Theme Settings</h2>
                <div class="theme-options" id="themeOptions">
                    <div class="theme-option selected" data-theme="icy">
                        <span class="icon">❄️</span>
                        <span class="name">Icy</span>
                    </div>
                    <div class="theme-option" data-theme="ocean">
                        <span class="icon">🌊</span>
                        <span class="name">Ocean</span>
                    </div>
                    <div class="theme-option" data-theme="dark">
                        <span class="icon">🌙</span>
                        <span class="name">Dark</span>
                    </div>
                </div>
                <p style="text-align:center;margin-top:20px;color:var(--text-muted);font-size:14px;">Theme saved automatically.</p>
            </div>
        </div>
    </div>

    <script>
        // ------------------------------------------------------------------
        // Globals
        // ------------------------------------------------------------------
        const TMDB_IMG = "https://image.tmdb.org/t/p/w500";
        const TMDB_THUMB = "https://image.tmdb.org/t/p/w92";

        let currentMedia = null;
        let currentDetails = null;
        let currentTVSeasons = [];

        let favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
        let history = JSON.parse(localStorage.getItem('history') || '[]');
        let currentTheme = localStorage.getItem('theme') || 'icy';
        let searchTimeout = null;

        // ------------------------------------------------------------------
        // API calls
        // ------------------------------------------------------------------
        async function apiFetch(endpoint, params = {}) {
            const url = new URL(endpoint, window.location.origin);
            Object.keys(params).forEach(k => url.searchParams.append(k, params[k]));
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('API error');
            return resp.json();
        }

        // ------------------------------------------------------------------
        // DOM refs
        // ------------------------------------------------------------------
        const heroContainer = document.getElementById('heroContainer');
        const rowsContainer = document.getElementById('rowsContainer');
        const searchInput = document.getElementById('searchInput');
        const searchBtn = document.getElementById('searchBtn');
        const suggestions = document.getElementById('suggestions');
        const searchSection = document.getElementById('searchSection');
        const searchGrid = document.getElementById('searchGrid');
        const searchResultTitle = document.getElementById('searchResultTitle');
        const favoritesSection = document.getElementById('favoritesSection');
        const favoritesGrid = document.getElementById('favoritesGrid');
        const modalOverlay = document.getElementById('modalOverlay');
        const modalBody = document.getElementById('modalBody');
        const modalClose = document.getElementById('modalClose');
        const settingsOverlay = document.getElementById('settingsOverlay');
        const settingsClose = document.getElementById('settingsClose');
        const settingsBtn = document.getElementById('settingsBtn');
        const navLinks = document.querySelectorAll('.nav-links a');

        // ------------------------------------------------------------------
        // Theme
        // ------------------------------------------------------------------
        function setTheme(theme) {
            document.body.className = theme;
            currentTheme = theme;
            localStorage.setItem('theme', theme);
            document.querySelectorAll('.theme-option').forEach(el => {
                el.classList.toggle('selected', el.dataset.theme === theme);
            });
        }
        setTheme(currentTheme);

        document.querySelectorAll('.theme-option').forEach(el => {
            el.addEventListener('click', () => setTheme(el.dataset.theme));
        });

        settingsBtn.addEventListener('click', () => settingsOverlay.classList.add('active'));
        settingsClose.addEventListener('click', () => settingsOverlay.classList.remove('active'));
        settingsOverlay.addEventListener('click', (e) => {
            if (e.target === settingsOverlay) settingsOverlay.classList.remove('active');
        });

        // ------------------------------------------------------------------
        // Navigation
        // ------------------------------------------------------------------
        function showSection(section) {
            document.getElementById('homeSection').classList.toggle('hidden', section !== 'home');
            document.getElementById('searchSection').classList.toggle('hidden', section !== 'search');
            document.getElementById('favoritesSection').classList.toggle('hidden', section !== 'favorites');
            navLinks.forEach(link => {
                link.classList.toggle('active', link.dataset.section === section);
            });
            if (section === 'favorites') renderFavorites();
            if (section === 'home') {
                if (!document.getElementById('heroContainer').children.length) loadHome();
            }
        }

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                showSection(link.dataset.section);
            });
        });

        // ------------------------------------------------------------------
        // Home
        // ------------------------------------------------------------------
        async function loadHome() {
            try {
                rowsContainer.innerHTML = '<div class="row"><div class="movie-grid">' + 
                    '<div class="loading-card"></div>'.repeat(6) + '</div></div>';

                const trending = await apiFetch('/api/trending');
                if (trending.results && trending.results.length) {
                    renderHero(trending.results[0]);
                }

                const rowConfigs = [
                    { title: '🔥 Trending Now', endpoint: '/api/trending' },
                    { title: '🎬 Now Playing', endpoint: '/api/now_playing' },
                    { title: '⭐ Top Rated', endpoint: '/api/top_rated', params: { type: 'movie' } },
                    { title: '📅 Upcoming', endpoint: '/api/upcoming' },
                ];

                rowsContainer.innerHTML = '';
                for (const config of rowConfigs) {
                    const data = await apiFetch(config.endpoint, config.params || {});
                    if (data.results && data.results.length) {
                        renderRow(config.title, data.results);
                    }
                }

                if (history.length) {
                    const historyItems = history.slice(-10).reverse().map(h => ({
                        id: h.id,
                        title: h.title,
                        year: h.year || '',
                        poster_path: h.poster_path || '',
                        media_type: h.type
                    }));
                    if (historyItems.length) {
                        renderRow('⏯️ Continue Watching', historyItems);
                    }
                }
            } catch (e) {
                console.error(e);
                rowsContainer.innerHTML = '<div class="row"><p style="color:var(--text-muted);text-align:center;">Failed to load content.</p></div>';
            }
        }

        function renderHero(item) {
            const title = item.title || item.name;
            const year = (item.release_date || item.first_air_date || '').slice(0,4);
            const overview = item.overview || '';
            const backdrop = item.backdrop_path ? `url(${TMDB_IMG}${item.backdrop_path})` : 'var(--bg-secondary)';
            const mediaType = item.media_type || (item.first_air_date ? 'tv' : 'movie');

            heroContainer.innerHTML = `
                <div class="hero" style="background-image: ${backdrop};">
                    <div class="hero-content">
                        <div class="hero-title">${title}</div>
                        <div class="hero-meta">
                            <span>${year}</span>
                            <span>${mediaType.toUpperCase()}</span>
                            <span>⭐ ${item.vote_average?.toFixed(1) || 'N/A'}</span>
                        </div>
                        <div class="hero-overview">${overview}</div>
                        <button class="hero-btn" data-id="${item.id}" data-type="${mediaType}">▶ Watch Now</button>
                    </div>
                </div>
            `;
            heroContainer.querySelector('.hero-btn').addEventListener('click', () => {
                openModal(item.id, mediaType);
            });
        }

        function renderRow(title, items) {
            const rowDiv = document.createElement('div');
            rowDiv.className = 'row';
            let html = `
                <div class="row-header">
                    <h3 class="row-title">${title}</h3>
                </div>
                <div class="movie-grid">
            `;
            for (const item of items) {
                const poster = item.poster_path ? `${TMDB_IMG}${item.poster_path}` : '';
                const titleText = item.title || item.name || 'Unknown';
                const year = (item.release_date || item.first_air_date || '').slice(0,4);
                const type = item.media_type || (item.first_air_date ? 'tv' : 'movie');
                html += `
                    <div class="movie-card" data-id="${item.id}" data-type="${type}">
                        ${poster ? `<img src="${poster}" alt="${titleText}" loading="lazy">` : '<div style="aspect-ratio:2/3;background:var(--bg-card);display:flex;align-items:center;justify-content:center;color:var(--text-muted);">No Image</div>'}
                        <div class="movie-card-info">
                            <div class="movie-card-title">${titleText}</div>
                            <div class="movie-card-year">${year}</div>
                        </div>
                        <span class="badge">${type}</span>
                    </div>
                `;
            }
            html += '</div></div>';
            rowDiv.innerHTML = html;
            rowsContainer.appendChild(rowDiv);

            rowDiv.querySelectorAll('.movie-card').forEach(card => {
                card.addEventListener('click', () => {
                    openModal(card.dataset.id, card.dataset.type);
                });
            });
        }

        // ------------------------------------------------------------------
        // Search & Live Suggestions
        // ------------------------------------------------------------------
        searchBtn.addEventListener('click', doSearch);
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                doSearch();
                closeSuggestions();
            }
        });

        searchInput.addEventListener('input', () => {
            const query = searchInput.value.trim();
            if (query.length < 2) {
                closeSuggestions();
                return;
            }
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => fetchSuggestions(query), 300);
        });

        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                closeSuggestions();
            }
        });

        async function fetchSuggestions(query) {
            try {
                const data = await apiFetch('/api/search', { q: query });
                if (data.results && data.results.length) {
                    showSuggestions(data.results.slice(0, 6));
                } else {
                    closeSuggestions();
                }
            } catch (e) {
                closeSuggestions();
            }
        }

        function showSuggestions(items) {
            suggestions.innerHTML = '';
            for (const item of items) {
                const div = document.createElement('div');
                div.className = 'suggestion-item';
                const poster = item.poster_path ? `${TMDB_THUMB}${item.poster_path}` : '';
                const title = item.title || item.name || 'Unknown';
                const year = (item.release_date || item.first_air_date || '').slice(0,4);
                const type = item.media_type || (item.first_air_date ? 'tv' : 'movie');
                div.innerHTML = `
                    ${poster ? `<img src="${poster}" alt="${title}">` : '<div style="width:40px;height:60px;background:var(--bg-card);border-radius:6px;"></div>'}
                    <div class="info">
                        <div class="title">${title}</div>
                        <div class="sub">${year} · ${type}</div>
                    </div>
                    <span class="badge-sm">${type}</span>
                `;
                div.addEventListener('click', () => {
                    closeSuggestions();
                    searchInput.value = title;
                    openModal(item.id, type);
                });
                suggestions.appendChild(div);
            }
            suggestions.classList.add('active');
        }

        function closeSuggestions() {
            suggestions.classList.remove('active');
            suggestions.innerHTML = '';
        }

        async function doSearch() {
            const query = searchInput.value.trim();
            if (!query) return;
            closeSuggestions();
            try {
                const data = await apiFetch('/api/search', { q: query });
                searchResultTitle.textContent = `🔍 Results for "${query}"`;
                searchGrid.innerHTML = '';
                if (data.results && data.results.length) {
                    for (const item of data.results) {
                        const card = createMovieCard(item);
                        searchGrid.appendChild(card);
                    }
                } else {
                    searchGrid.innerHTML = '<div class="empty-state">No results found. ❄️</div>';
                }
                showSection('search');
            } catch (e) {
                console.error(e);
                alert('Search failed.');
            }
        }

        function createMovieCard(item) {
            const div = document.createElement('div');
            div.className = 'movie-card';
            div.dataset.id = item.id;
            div.dataset.type = item.media_type || (item.first_air_date ? 'tv' : 'movie');
            const poster = item.poster_path ? `${TMDB_IMG}${item.poster_path}` : '';
            const title = item.title || item.name || 'Unknown';
            const year = (item.release_date || item.first_air_date || '').slice(0,4);
            div.innerHTML = `
                ${poster ? `<img src="${poster}" alt="${title}" loading="lazy">` : '<div style="aspect-ratio:2/3;background:var(--bg-card);display:flex;align-items:center;justify-content:center;color:var(--text-muted);">No Image</div>'}
                <div class="movie-card-info">
                    <div class="movie-card-title">${title}</div>
                    <div class="movie-card-year">${year}</div>
                </div>
                <span class="badge">${div.dataset.type}</span>
            `;
            div.addEventListener('click', () => {
                openModal(item.id, div.dataset.type);
            });
            return div;
        }

        // ------------------------------------------------------------------
        // Favorites
        // ------------------------------------------------------------------
        function renderFavorites() {
            favoritesGrid.innerHTML = '';
            if (!favorites.length) {
                favoritesGrid.innerHTML = '<div class="empty-state">No favorites yet. ❄️</div>';
                return;
            }
            for (const fav of favorites) {
                const div = document.createElement('div');
                div.className = 'movie-card';
                div.dataset.id = fav.id;
                div.dataset.type = fav.type;
                const poster = fav.poster_path ? `${TMDB_IMG}${fav.poster_path}` : '';
                div.innerHTML = `
                    ${poster ? `<img src="${poster}" alt="${fav.title}" loading="lazy">` : '<div style="aspect-ratio:2/3;background:var(--bg-card);display:flex;align-items:center;justify-content:center;color:var(--text-muted);">No Image</div>'}
                    <div class="movie-card-info">
                        <div class="movie-card-title">${fav.title}</div>
                        <div class="movie-card-year">${fav.year || ''}</div>
                    </div>
                    <span class="badge">${fav.type}</span>
                `;
                div.addEventListener('click', () => {
                    openModal(fav.id, fav.type);
                });
                favoritesGrid.appendChild(div);
            }
        }

        // ------------------------------------------------------------------
        // Modal
        // ------------------------------------------------------------------
        async function openModal(id, type) {
            try {
                const details = await apiFetch(`/api/${type}/${id}`);
                currentDetails = details;
                currentMedia = { id, type, title: details.title || details.name };

                const title = details.title || details.name;
                const year = (details.release_date || details.first_air_date || '').slice(0,4);
                const rating = details.vote_average?.toFixed(1) || 'N/A';
                const runtime = details.runtime || (details.episode_run_time ? details.episode_run_time[0] : null);
                const runtimeStr = runtime ? `${runtime} min` : '';
                const overview = details.overview || 'No overview available.';
                const genres = (details.genres || []).map(g => g.name).join(', ');
                const cast = (details.credits?.cast || []).slice(0,8).map(c => c.name).join(', ');
                const poster = details.poster_path ? `${TMDB_IMG}${details.poster_path}` : '';

                const isFavorite = favorites.some(f => f.id == id && f.type === type);

                let html = `
                    <div class="modal-top">
                        <div class="modal-poster">
                            ${poster ? `<img src="${poster}" alt="${title}">` : '<div style="aspect-ratio:2/3;background:var(--bg-card);border-radius:10px;"></div>'}
                        </div>
                        <div class="modal-details">
                            <div class="modal-title">${title}</div>
                            <div class="modal-meta">
                                <span>${year}</span>
                                <span>⭐ ${rating}</span>
                                ${runtimeStr ? `<span>🕒 ${runtimeStr}</span>` : ''}
                                <span>${type.toUpperCase()}</span>
                            </div>
                            <div class="modal-genres">
                                ${genres ? genres.split(',').map(g => `<span>${g.trim()}</span>`).join('') : ''}
                            </div>
                            <div class="modal-overview">${overview}</div>
                            <div class="modal-cast"><strong>Cast:</strong> ${cast || 'N/A'}</div>
                            <div>
                                <button class="favorite-btn ${isFavorite ? 'active' : ''}" id="favToggle">${isFavorite ? '⭐ Favorited' : '☆ Add to Favorites'}</button>
                            </div>
                        </div>
                    </div>
                    <div class="watch-section">
                `;

                if (type === 'tv') {
                    const seasons = details.seasons || [];
                    const seasonOptions = seasons.filter(s => s.season_number > 0).map(s => 
                        `<option value="${s.season_number}">Season ${s.season_number}</option>`
                    ).join('');
                    html += `
                        <div class="tv-selectors">
                            <label>Season <select id="seasonSelect">${seasonOptions}</select></label>
                            <label>Episode <select id="episodeSelect"><option value="1">1</option></select></label>
                        </div>
                        <button class="watch-btn" id="watchBtn">▶ Watch Episode</button>
                    `;
                } else {
                    html += `<button class="watch-btn" id="watchBtn">▶ Watch Movie</button>`;
                }

                html += `</div>`;

                modalBody.innerHTML = html;
                modalOverlay.classList.add('active');

                document.getElementById('modalClose').onclick = closeModal;
                modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) closeModal(); });

                document.getElementById('favToggle').addEventListener('click', () => {
                    toggleFavorite(id, type, title, poster, year);
                });

                document.getElementById('watchBtn').addEventListener('click', () => {
                    let season, episode;
                    if (type === 'tv') {
                        season = parseInt(document.getElementById('seasonSelect').value);
                        episode = parseInt(document.getElementById('episodeSelect').value);
                        if (!season || !episode) { alert('Please select season and episode.'); return; }
                    }
                    watchContent(id, type, season, episode);
                });

                if (type === 'tv') {
                    const seasonSelect = document.getElementById('seasonSelect');
                    const episodeSelect = document.getElementById('episodeSelect');
                    seasonSelect.addEventListener('change', () => {
                        const s = parseInt(seasonSelect.value);
                        fetchTVSeason(id, s).then(seasonData => {
                            if (seasonData && seasonData.episodes) {
                                episodeSelect.innerHTML = seasonData.episodes.map((ep, i) => 
                                    `<option value="${i+1}">${i+1}</option>`
                                ).join('');
                            }
                        }).catch(() => {});
                    });
                    if (seasonSelect.options.length) {
                        seasonSelect.dispatchEvent(new Event('change'));
                    }
                }

            } catch (e) {
                console.error(e);
                alert('Error loading details.');
            }
        }

        function closeModal() {
            // Release the player iframe so audio and network activity stop
            // when the watch modal is closed.
            modalBody.querySelectorAll('iframe').forEach(frame => {
                frame.src = 'about:blank';
                frame.remove();
            });
            modalBody.innerHTML = '';
            modalOverlay.classList.remove('active');
        }

        async function fetchTVSeason(id, season) {
            const resp = await fetch(`/api/tv/${id}/season/${season}`);
            if (!resp.ok) throw new Error('Failed to fetch season');
            return resp.json();
        }

        // ------------------------------------------------------------------
        // Watch
        // ------------------------------------------------------------------
        function watchContent(id, type, season, episode) {
            let url;
            if (type === 'movie') {
                url = `https://player.videasy.net/movie/${id}`;
            } else {
                url = `https://player.videasy.net/tv/${id}/${season}/${episode}`;
            }
            modalBody.innerHTML = `
                <div style="position:relative;padding-bottom:56.25%;height:0;">
                    <iframe src="${url}" style="position:absolute;top:0;left:0;width:100%;height:100%;" frameborder="0" allowfullscreen allow="encrypted-media"></iframe>
                </div>
                <button class="modal-close" style="position:absolute;top:10px;right:20px;background:rgba(0,0,0,0.5);border:none;color:#fff;font-size:28px;width:40px;height:40px;border-radius:50%;cursor:pointer;" onclick="closeModal()">&times;</button>
            `;
            addHistory(id, currentDetails?.title || currentMedia?.title || 'Unknown', type, currentDetails?.poster_path || '', season, episode);
        }

        // ------------------------------------------------------------------
        // Favorites & History helpers
        // ------------------------------------------------------------------
        function toggleFavorite(id, type, title, poster, year) {
            const idx = favorites.findIndex(f => f.id == id && f.type === type);
            if (idx >= 0) {
                favorites.splice(idx, 1);
            } else {
                favorites.push({ id, type, title, poster_path: poster, year });
            }
            localStorage.setItem('favorites', JSON.stringify(favorites));
            const btn = document.getElementById('favToggle');
            if (btn) {
                const isFav = favorites.some(f => f.id == id && f.type === type);
                btn.textContent = isFav ? '⭐ Favorited' : '☆ Add to Favorites';
                btn.classList.toggle('active', isFav);
            }
            if (!document.getElementById('favoritesSection').classList.contains('hidden')) {
                renderFavorites();
            }
        }

        function addHistory(id, title, type, poster, season, episode) {
            history = history.filter(h => h.id != id || h.type != type);
            history.push({
                id,
                title,
                type,
                poster_path: poster || '',
                year: currentDetails?.release_date?.slice(0,4) || currentDetails?.first_air_date?.slice(0,4) || '',
                timestamp: Date.now()
            });
            if (history.length > 50) history = history.slice(-50);
            localStorage.setItem('history', JSON.stringify(history));
            // Refresh home if visible
            if (!document.getElementById('homeSection').classList.contains('hidden')) {
                setTimeout(() => loadHome(), 500);
            }
        }

        // ------------------------------------------------------------------
        // Navbar scroll effect
        // ------------------------------------------------------------------
        window.addEventListener('scroll', () => {
            const nav = document.getElementById('navbar');
            if (window.scrollY > 50) nav.classList.add('scrolled');
            else nav.classList.remove('scrolled');
        });

        // ------------------------------------------------------------------
        // Init
        // ------------------------------------------------------------------
        loadHome();
    </script>
</body>
</html>
"""

# ----------------------------------------------------------------------
# Flask Routes (proxy to TMDB)
# ----------------------------------------------------------------------

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/search')
def search():
    q = request.args.get('q', '')
    if not q:
        return jsonify({'results': []})
    url = f"{TMDB_BASE}/search/multi"
    params = {'api_key': TMDB_API_KEY, 'query': q, 'page': 1}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

@app.route('/api/trending')
def trending():
    url = f"{TMDB_BASE}/trending/all/week"
    params = {'api_key': TMDB_API_KEY}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

@app.route('/api/now_playing')
def now_playing():
    url = f"{TMDB_BASE}/movie/now_playing"
    params = {'api_key': TMDB_API_KEY}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

@app.route('/api/upcoming')
def upcoming():
    url = f"{TMDB_BASE}/movie/upcoming"
    params = {'api_key': TMDB_API_KEY}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

@app.route('/api/top_rated')
def top_rated():
    media_type = request.args.get('type', 'movie')
    url = f"{TMDB_BASE}/{media_type}/top_rated"
    params = {'api_key': TMDB_API_KEY}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

@app.route('/api/movie/<int:id>')
def movie_details(id):
    url = f"{TMDB_BASE}/movie/{id}"
    params = {'api_key': TMDB_API_KEY, 'append_to_response': 'credits'}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

@app.route('/api/tv/<int:id>')
def tv_details(id):
    url = f"{TMDB_BASE}/tv/{id}"
    params = {'api_key': TMDB_API_KEY, 'append_to_response': 'credits'}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

@app.route('/api/tv/<int:id>/season/<int:season>')
def tv_season(id, season):
    url = f"{TMDB_BASE}/tv/{id}/season/{season}"
    params = {'api_key': TMDB_API_KEY}
    resp = requests.get(url, params=params)
    return jsonify(resp.json())

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)