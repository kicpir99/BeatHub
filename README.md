# 🎵 BeatHub - Modern Music Streaming Platform

[🇵🇱 Przejdź do polskiej wersji (Polish Version)](#-beathub---nowoczesna-platforma-streamingowa-pl)

BeatHub is a modern, fully responsive music streaming web application built with the **Django** framework. The project stands out with an innovative User Interface (UI/UX) reminiscent of industry-leading streaming platforms, enriched with unique music discovery and navigation features.

---

## ✨ Key Features

* **Global, Uninterrupted Music Player:** Powered by **Turbo (Hotwired)**, navigating through different pages does not interrupt the audio playback. The player remains consistently anchored at the bottom of the screen.
* **Discovery Mode:** A unique, interactive "card" system (inspired by dating apps) that allows users to quickly listen to song snippets and swipe to either like or skip them.
* **Advanced Queue Management:** Seamlessly add tracks to the playback queue with a fluid, globally accessible interface.
* **Artist Profiles & Albums:** Rich detail pages for artists (featuring dynamically generated biographies) and comprehensive album listings complete with production credits.
* **Playlists & Likes System:** Create private and public playlists, and "like" individual tracks or entire albums.
* **Modern Design (Tailwind CSS):** An aesthetic interface featuring "Glassmorphism", smooth animations (including an animated equalizer and volume gradients), fully optimized for both mobile and desktop devices.
* **Dynamic Audio Visualizer:** Real-time audio frequency analysis displayed directly on the player interface.

---

## 🛠 Tech Stack

* **Backend:** Python 3, Django 6.x
* **Database:** SQLite (ideal for local testing and portfolio showcases)
* **Frontend:** HTML5, JavaScript (Vanilla), Tailwind CSS (integrated via CDN)
* **SPA-like Navigation:** Turbo (Hotwired) for dynamic content reloading without refreshing the music player.
* **Data Generation (Seeder):** `Faker` library (localized), `Mutagen` (for precise MP3 length extraction), and `Requests` for downloading placeholder images.

---

## 🚀 Quick Start

The application is designed to be launched instantly. It includes a robust *Seeder* script that generates a fully functional database with images, profiles, and song relations within seconds.

### Prerequisites:
* Python 3.10 or newer

### Step-by-Step Guide:

1. **Clone the repository:**
   ```bash
   git clone <REPOSITORY_LINK>
   cd <PROJECT_FOLDER>
   ```

2. **Create and activate a virtual environment:**
   * **Windows:**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   * **Linux/Mac:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Apply database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Populate the database with sample data (Seeder):**
   *(This script automatically generates users, artists, music genres, playlists, and tens of thousands of historical plays for statistical purposes).*
   ```bash
   python manage.py seed_db
   ```

6. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

7. Open your browser and navigate to: **http://127.0.0.1:8000/**

---

## 🔑 Login Information
Thanks to the Seeder, random users are added to the database. However, you can easily register a **new account** using the built-in form on the website or create a superuser (Admin Panel) by typing the following in your terminal:
```bash
python manage.py createsuperuser
```

---

## 📂 File Structure
* `music/` - The main Django app containing models (profiles, catalog), views, and the routing system.
* `music/templates/` - Component-based HTML templates.
* `music/static/music/js/` - Complex frontend logic (e.g., `player.js` handling uninterrupted playback and `discovery.js`).
* `music/management/commands/seed_db.py` - Advanced database population script.
* `media/` - (Partially excluded in .gitignore) contains track templates used to clone new songs, and downloaded cover images.

<br><br>

---
---

# 🇵🇱 BeatHub - Nowoczesna Platforma Streamingowa (PL)

[🇬🇧 Go to English version](#-beathub---modern-music-streaming-platform)

BeatHub to nowoczesna, w pełni responsywna aplikacja internetowa do strumieniowania muzyki, zbudowana przy użyciu frameworka **Django**. Projekt wyróżnia się innowacyjnym podejściem do interfejsu użytkownika (UI/UX), przypominającym wiodące platformy streamingowe, wzbogaconym o unikalne funkcje nawigacji i odkrywania muzyki.

---

## ✨ Główne funkcjonalności

* **Globalny, nieprzerwany Odtwarzacz Muzyki:** Dzięki technologii **Turbo (Hotwired)**, nawigacja po podstronach aplikacji nie przerywa odtwarzania utworu. Odtwarzacz zawsze widnieje na dole ekranu.
* **Tryb Discovery (Odkrywaj):** Unikalny system interaktywnych "kart" (inspirowany aplikacjami randkowymi), pozwalający na szybkie odsłuchiwanie fragmentów utworów i przesuwanie ich, aby dodać je do ulubionych lub pominąć.
* **Zaawansowane zarządzanie listą odtwarzania (Kolejka):** Możliwość dodawania utworów do kolejki, z płynnym, globalnym interfejsem odtwarzania.
* **Profile Artystów i Albumy:** Bogate strony szczegółowe dla artystów (z generowanymi biografiami) oraz pełne wykazy albumów z informacjami o producentach.
* **System Playlist i Polubień:** Tworzenie prywatnych oraz publicznych playlist, możliwość polubienia pojedynczych utworów, jak i całych albumów.
* **Nowoczesny Design (Tailwind CSS):** Estetyczny interfejs wspierający efekt "Glassmorphism", płynne animacje (w tym animowany equalizer i gradienty głośności) stworzony z myślą o urządzeniach mobilnych i desktopach.
* **Dynamiczny Wizualizator Audio:** Analiza pasma odtwarzanego dźwięku w czasie rzeczywistym wyświetlana na interfejsie odtwarzacza.

---

## 🛠 Technologie

* **Backend:** Python 3, Django 6.x
* **Baza danych:** SQLite (idealna do testowania i prezentacji lokalnej)
* **Frontend:** HTML5, JavaScript (Vanilla), Tailwind CSS (zintegrowany przez CDN)
* **Nawigacja SPA-like:** Turbo (Hotwired) do dynamicznego przeładowywania zawartości bez odświeżania odtwarzacza.
* **Generowanie danych (Seeder):** Biblioteka `Faker` (lokalizacja polska), `Mutagen` (do precyzyjnego odczytywania długości plików MP3) oraz `Requests` do pobierania zdjęć.

---

## 🚀 Szybki start

Aplikacja została przygotowana z myślą o błyskawicznym uruchomieniu. Zawiera profesjonalny skrypt *Seeder*, który w kilkanaście sekund wygeneruje w pełni funkcjonalną bazę danych ze zdjęciami, profilami i powiązaniami utworów.

### Wymagania wstępne:
* Python 3.10 lub nowszy

### Krok po kroku:

1. **Sklonuj repozytorium:**
   ```bash
   git clone <LINK_DO_REPOZYTORIUM>
   cd <FOLDER_PROJEKTU>
   ```

2. **Utwórz i aktywuj wirtualne środowisko:**
   * **Windows:**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   * **Linux/Mac:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Zainstaluj wymagane pakiety:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Wykonaj migracje bazy danych:**
   ```bash
   python manage.py migrate
   ```

5. **Zasil bazę danych przykładowymi danymi (Seeder):**
   *(Skrypt automatycznie wygeneruje użytkowników, artystów, gatunki muzyczne, playlisty oraz dziesiątki tysięcy historycznych odtworzeń dla statystyk).*
   ```bash
   python manage.py seed_db
   ```

6. **Uruchom serwer developerski:**
   ```bash
   python manage.py runserver
   ```

7. Otwórz przeglądarkę i wejdź pod adres: **http://127.0.0.1:8000/**

---

## 🔑 Informacje o logowaniu
Dzięki zastosowaniu Seedera do bazy dodani zostali losowi użytkownicy. Możesz jednak bez problemu zarejestrować **nowe konto** za pomocą wbudowanego na stronie formularza lub utworzyć superużytkownika (Panel Admina), wpisując w terminalu:
```bash
python manage.py createsuperuser
```

---

## 📂 Struktura plików
* `music/` - Główna aplikacja Django zawierająca modele (profile, katalog), widoki oraz system routing'u.
* `music/templates/` - Szablony HTML oparte o komponenty.
* `music/static/music/js/` - Złożona logika frontendu (m.in. `player.js` obsługujący bezprzerwowe odtwarzanie i `discovery.js`).
* `music/management/commands/seed_db.py` - Zaawansowany skrypt wypełniający bazę.
* `media/` - (Częściowo wykluczona w .gitignore) zawiera szablony utworów, na bazie których klonowane są nowe piosenki, oraz pobierane okładki.
