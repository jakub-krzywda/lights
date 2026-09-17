# Skrypt sterujący DMX (uDMX + OLA) — założenia

## Kontekst

Raspberry Pi 3 z podłączonym interfejsem USB-DMX **uDMX** (anyma.ch, vendor:product `16c0:05dc`), sterującym ledbarem (fixture typu "Generic RGB Panel") przez DMX512.

Warstwa sieciowa/bridge (OLA + Art-Net) jest już skonfigurowana i przetestowana:
- OLA (Open Lighting Architecture) zainstalowane na RPi, plugin `usbdmx` aktywny
- Universe 1 spatchowane: output → Anyma USB Device (uDMX)
- Test `ola_set_dmx -u 1 -d 255,0,0,0,0` **działa** — ledbar reaguje poprawnie

To potwierdza, że cały łańcuch RPi→USB→uDMX→DMX→ledbar jest sprawny. Zadaniem tego skryptu jest zastąpienie ręcznego `ola_set_dmx` i GUI (QLC+) wygodną warstwą sterowania programowego.

## Cel skryptu

Skrypt Python działający **lokalnie na RPi**, sterujący ledbarem przez lokalne Python API OLA (bez pośrednictwa sieci Art-Net/QLC+).

## Środowisko docelowe

- Raspberry Pi 3, Raspbian/Debian
- OLA + `python3-ola` zainstalowane (`sudo apt install python3-ola`)
- Universe DMX: **1**
- Fixture: ledbar RGB, adres startowy DMX = kanał 1 (do potwierdzenia — sprawdzić fizyczne dip-switche/ustawienia na ledbarze), 3 kanały (R, G, B) — **do zweryfikowania z instrukcją ledbara**, może mieć więcej kanałów (np. dimmer, strobe, tryby)

## Funkcjonalność (do ustalenia poziom pierwszej iteracji)

Minimalny zakres (v1):
- Funkcja `send_dmx(universe: int, channels: dict[int, int])` — wysyła słownik {kanał: wartość 0-255} do danego universum przez `ola.ClientWrapper`
- Blackout (wyzerowanie wszystkich kanałów)
- Ustawienie koloru RGB na ledbarze (funkcja wysokopoziomowa, np. `set_color(r, g, b)`, mapująca na konkretne kanały startowe fixture)

Do rozważenia w kolejnych iteracjach (nie wymagane teraz):
- Płynne przejścia/fade między kolorami
- Predefiniowane sceny/presety
- Prosty interfejs sterowania (CLI interaktywne, terminal UI, albo lekki webowy)
- Reakcja na dźwięk/muzykę (wspomniane wcześniej jako pomysł, nieprecyzowane)

## Wymagania techniczne

- Python 3 (wersja zgodna z tym, co jest na RPi — sprawdzić `python3 --version`)
- Biblioteka: `python3-ola` (pakiet systemowy, nie pip)
- Kod ma działać jako skrypt uruchamiany lokalnie na RPi (SSH albo bezpośrednio)

## Znane ograniczenia / uwagi

- `ClientWrapper` z OLA korzysta z pętli zdarzeń (`wrapper.Run()`) — trzeba to wziąć pod uwagę projektując interfejs (np. jednorazowe wysłanie vs. pętla ciągła/interaktywna)
- Adres DMX ledbara (kanał startowy) nie został jeszcze jawnie potwierdzony — pierwszy krok w Claude Code: zweryfikować to fizycznie na urządzeniu, zanim napisze się `set_color()`
- Liczba kanałów ledbara (czy to tylko RGB, czy więcej — np. RGBW, dimmer) — do sprawdzenia w dokumentacji/etykiecie urządzenia

## Otwarte pytania do ustalenia podczas pracy nad skryptem

1. Ile kanałów ma ledbar i co robi każdy z nich (R/G/B/dimmer/strobe/tryb)?
2. Jaki jest adres startowy DMX ustawiony fizycznie na ledbarze?
3. Czy skrypt ma działać jednorazowo (ustaw i wyjdź) czy jako długo działający proces (np. z interaktywnym sterowaniem)?
4. Czy w pierwszej iteracji wystarczy CLI, czy od razu potrzebny jakiś prosty UI?
</file_text>