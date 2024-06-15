import random
import sys
from multiprocessing import Process, Queue
from typer import Typer, Argument
from rich.console import Console
from rich.table import Table

app = Typer()
console = Console()

# Funktion zum Einlesen der Buzzwords aus einer Datei
def read_buzzwords(wordfile):
    with open(wordfile, 'r', encoding='utf-8') as file:
        words = [line.strip() for line in file if line.strip()]
    return words

# Funktion zur Generierung einer Bingo-Karte
def generate_bingo_card(xaxis, yaxis, buzzwords):
    card = []
    for _ in range(yaxis):
        row = random.sample(buzzwords, xaxis)
        card.append(row)
    return card

# Funktion zur Anzeige der Bingo-Karte mit Rich
def display_bingo_card(card):
    table = Table(show_header=False, box=None)
    for row in card:
        table.add_row(*row)
    console.print(table)

# Funktion zum Überprüfen, ob ein Bingo erreicht wurde
def check_bingo(card):
    # Überprüfen der Spalten
    for col in range(len(card[0])):
        if all(cell == "X" for cell in [card[row][col] for row in range(len(card))]):
            return True

    # Überprüfen der Zeilen
    for row in card:
        if all(cell == "X" for cell in row):
            return True

    # Überprüfen der Diagonalen
    if all(card[i][i] == "X" for i in range(len(card))) or \
            all(card[i][len(card)-1-i] == "X" for i in range(len(card))):
        return True

    return False

# Funktion für den Spielprozess eines Spielers
def play_game(player_id, xaxis, yaxis, buzzwords, queue, result_queue):
    bingo_card = generate_bingo_card(xaxis, yaxis, buzzwords)
    console.print(f"Spieler {player_id}: Hier ist deine Bingo-Karte:")
    display_bingo_card(bingo_card)

    while True:
        field = queue.get()  # Warten auf die Eingabe des Hauptprozesses
        if field == "exit":
            break
        row, col = map(int, field.split(","))
        console.print(f"Spieler {player_id}: Markiere {bingo_card[row][col]}")
        bingo_card[row][col] = "X"
        display_bingo_card(bingo_card)

        if check_bingo(bingo_card):
            console.print(f"Spieler {player_id}: Bingo! Ich habe gewonnen!")
            result_queue.put(player_id)  # Spieler-ID an den Hauptprozess senden
            break

# Hauptfunktion zum Starten des Spiels
@app.command()
def start(xaxis: int = Argument(5, help="Anzahl der Felder in der Breite"),
          yaxis: int = Argument(5, help="Anzahl der Felder in der Höhe"),
          wordfile: str = Argument(..., help="Pfad zur Textdatei mit Buzzwords")):

    buzzwords = read_buzzwords(wordfile)
    if len(buzzwords) < xaxis * yaxis:
        console.print("Die Textdatei enthält nicht genügend Buzzwords für die angegebene Kartengröße.")
        sys.exit(1)

    num_players = 1

    input_queues = []
    result_queue = Queue()
    processes = []

    for i in range(num_players):
        queue = Queue()
        process = Process(target=play_game, args=(i + 1, xaxis, yaxis, buzzwords, queue, result_queue))
        process.start()
        processes.append(process)
        input_queues.append(queue)

    while True:
        console.print("Gib die Zeile und Spalte des Feldes ein, das du markieren möchtest (z.B. 0,1) oder 'exit' zum Beenden:")
        field = input().strip()
        if field == "exit":
            for queue in input_queues:
                queue.put("exit")
            break
        for queue in input_queues:
            queue.put(field)

        if not result_queue.empty():
            winner = result_queue.get()
            console.print(f"Spieler {winner} hat gewonnen!")
            break

    for process in processes:
        process.terminate()

# Funktion zum Beitreten zum Spiel
@app.command()
def join(player_id: int = Argument(..., help="Die ID des Spielers, der beitreten möchte"),
         xaxis: int = Argument(5, help="Anzahl der Felder in der Breite"),
         yaxis: int = Argument(5, help="Anzahl der Felder in der Höhe"),
         wordfile: str = Argument(..., help="Pfad zur Textdatei mit Buzzwords")):

    buzzwords = read_buzzwords(wordfile)
    queue = Queue()
    result_queue = Queue()

    process = Process(target=play_game, args=(player_id, xaxis, yaxis, buzzwords, queue, result_queue))
    process.start()

    while True:
        console.print("Gib die Zeile und Spalte des Feldes ein, das du markieren möchtest (z.B. 0,1) oder 'exit' zum Beenden:")
        field = input().strip()
        if field == "exit":
            queue.put("exit")
            break
        queue.put(field)

        if not result_queue.empty():
            winner = result_queue.get()
            console.print(f"Spieler {winner} hat gewonnen!")
            break

    process.terminate()

if __name__ == "__main__":
    app()