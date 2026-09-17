# Skrypt sterujący DMX (uDMX + OLA) — założenia

## Kontekst

Raspberry Pi 3 z podłączonym interfejsem USB-DMX **uDMX** (anyma.ch, vendor:product `16c0:05dc`), sterującym ledbarem [Fun Generation LED BARbara 24](https://www.thomann.pl/fun_generation_led_barbara_24.htm) (24 LED RGB w 8 segmentach) przez DMX512.

Warstwa sieciowa/bridge (OLA + Art-Net) jest już skonfigurowana i przetestowana:
- OLA (Open Lighting Architecture) zainstalowane na RPi, plugin `usbdmx` aktywny
- Universe 1 spatchowane: output → Anyma USB Device (uDMX)
- Test `ola_set_dmx -u 1 -d 255,0,0,0,0` **działa** — ledbar reaguje poprawnie

To potwierdza, że cały łańcuch RPi→USB→uDMX→DMX→ledbar jest sprawny. Zadaniem tego skryptu jest zastąpienie ręcznego `ola_set_dmx` i GUI (QLC+) wygodną warstwą sterowania programowego.

## Cel skryptu

Skrypt Python działający **lokalnie na RPi**, sterujący ledbarem przez lokalne Python API OLA (bez pośrednictwa sieci Art-Net/QLC+).

## Środowisko docelowe

- Raspberry Pi 3, Raspbian/Debian
- OLA + `ola-python` zainstalowane (`sudo apt install ola-python`) — pakiet `python3-ola` nie istnieje w Debianie, właściwa nazwa to `ola-python`
- Universe DMX: **1**
- Fixture: Fun Generation LED BARbara 24. Adres DMX i tryb kanałów ustawia się w menu na wyświetlaczu urządzenia (przyciski MODE/SETUP/UP/DOWN), **nie dip-switchami**. Urządzenie wspiera 4 tryby: 2/3/5/24-kanałowy (patrz instrukcja producenta, rozdział 7.4–7.7). Skonfigurowano: **adres startowy 1, tryb 3-kanałowy (`3-ch`)**:
  - kanał 1 = R, kanał 2 = G, kanał 3 = B (intensywność 0–255)
  - tryb 5-ch dodaje kanał 4 = dimmer (musi być >0, inaczej nic nie widać) i kanał 5 = strobe
  - tryb 24-ch daje osobną kontrolę R/G/B dla każdego z 8 segmentów (kanały 1-24)

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
- Biblioteka: `ola-python` (pakiet systemowy, nie pip)
- Kod ma działać jako skrypt uruchamiany lokalnie na RPi (SSH albo bezpośrednio)

## Znane ograniczenia / uwagi

- `ClientWrapper` z OLA korzysta z pętli zdarzeń (`wrapper.Run()`) — trzeba to wziąć pod uwagę projektując interfejs (np. jednorazowe wysłanie vs. pętla ciągła/interaktywna)
- `OlaClient.SendDmx` oczekuje `array.array('B', ...)`, nie `bytearray` (woła wewnętrznie `.tobytes()`)
- Ledbar nie może być podłączony za dimmerem (info z instrukcji producenta) — zasilanie musi iść bezpośrednio z sieci

## Status otwartych pytań

1. ~~Ile kanałów ma ledbar i co robi każdy z nich~~ — rozstrzygnięte, patrz "Środowisko docelowe" i instrukcja producenta (rozdz. 7.4–7.7).
2. ~~Jaki jest adres startowy DMX~~ — ustawiony na urządzeniu na `d001` (kanał 1), tryb `3-ch`.
3. Czy skrypt ma działać jednorazowo czy jako długo działający proces — zaimplementowano oba warianty (`color`/`blackout` jednorazowo, `interactive` jako pętla).
4. Czy w pierwszej iteracji wystarczy CLI — tak, zaimplementowano CLI (`dmx_control.py`).
</file_text>