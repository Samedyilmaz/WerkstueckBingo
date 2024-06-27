# Importieren der erforderlichen Module
import os
import random
import typer
import logging
from datetime import datetime
import signal
from rich.console import Console
from rich.table import Table
from posix_ipc import MessageQueue, ExistentialError, O_CREAT, O_EXCL, O_RDWR

app = typer.Typer()
console = Console()

# Initialisierung der Message Queue Namen
settings_queue_name = "/buzzword_bingo_settings_queue"
result_queue_name = "/buzzword_bingo_result_queue"

# Funktion zum Einlesen der Buzzwords aus einer Datei
def load_buzzwords(filename: str):
    with open(filename, 'r') as file:
        buzzwords = [line.strip() for line in file.readlines()]
    return buzzwords

# Funktion zur Generierung einer Bingo-Karte
def create_bingo_card(buzzwords, xaxis: int, yaxis: int):
    selected_words = random.sample(buzzwords, xaxis * yaxis)
    card = [selected_words[i:i + xaxis] for i in range(0, len(selected_words), xaxis)]
    if xaxis == yaxis and (xaxis == 5 or xaxis == 7):  # Bedingung für den Joker
        middle = xaxis // 2
        card[middle][middle] = "FREI"
    return card

# Funktion zur Anzeige der Bingo-Karte mit Rich
def print_bingo_card(card, marks):
    table = Table(show_header=False)
    for i in range(len(card[0])):
        table.add_column(str(i+1))

    for y, row in enumerate(card):
        table.add_row(*[f"[green]{word}[/green]" if marks[y][x] or word == "FREI" else word for x, word in enumerate(row)])
    
    console.print(table)

# Funktion zum Überprüfen, ob ein Bingo erreicht wurde
def check_winner(marks):
    size = len(marks)
    for i in range(size):
        if all(marks[i]) or all(row[i] for row in marks):
            return True
    if all(marks[i][i] for i in range(size)) or all(marks[i][size - 1 - i] for i in range(size)):
        return True
    return False

# Funktion zum Empfangen einer Gewinnbenachrichtigung eines Spielers durch die result_message_queue
def receive_messages(result_mq, parent_pid, logger):
    while True:
        msg, _ = result_mq.receive()
        message = msg.decode()
        if "gewinnt" in message:
            console.print(f"[bold yellow]{message}[/bold yellow]")
            logger.info("Niederlage")
            logger.info("Ende des Spiels")
            result_mq.close() # Schließen und Löschen der result_mq
            result_mq.unlink()
            os.kill(parent_pid, signal.SIGTERM)
            os._exit(0)

# Funktion zum Setup des Loggers bzw. zum Erstellen der Logfile
def setup_logger(player_number):
    now = datetime.now()
    log_filename = now.strftime(f"%Y-%m-%d-%H-%M-%S-bingo-Spieler{player_number}.txt")
    logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d-%H-%M-%S')
    return logging.getLogger()

# Hauptfunktion zum Starten des Spiels und des ersten Spielerprozesses (Host)
@app.command()
def start(buzzwords_file: str, xaxis: int, yaxis: int):
    
    # Prüfen, ob die Buzzword-Datei mit dem angegebenen Namen existiert
    try:
        buzzwords = load_buzzwords(buzzwords_file)
    except (FileNotFoundError):
        console.print("[bold red]Buzzword-Datei nicht gefunden[/bold red]")
        return
    
    # Überprüfen, ob die Textdatei genügend Buzzwords für die angegebene Kartengröße enthält
    if len(buzzwords) < xaxis * yaxis:
        console.print("[bold red]Die Textdatei enthält nicht genügend Buzzwords für die angegebene Kartengröße[/bold red]")
        os._exit(0)

    name = input("Geben Sie Ihren Namen ein: ")
    player_number = 1

    # Nachrichtenwarteschlangen für Spieleinstellungen und Gewinnbenachrichtigung erstellen
    try:
        settings_mq = MessageQueue(settings_queue_name, flags=O_CREAT | O_EXCL, mode=0o666)
        result_mq = MessageQueue(result_queue_name, flags=O_CREAT | O_EXCL, mode=0o666)
        console.print("Spiel erstellt. Warten auf Spieler...")
        console.print(f"Spieler: [bold yellow]{name}[/bold yellow]")
    except ExistentialError:
        console.print("Spiel läuft bereits. Trete dem bestehenden Spiel bei.")
        return
    
    # Start des Loggers
    logger = setup_logger(player_number)
    logger.info("Start des Spiels")
    logger.info(f"Größe des Spielfelds: ({xaxis}/{yaxis})")
    
    # Sendet Spieleinstellungen zum beitretenden Spieler
    settings_message = f"{xaxis},{yaxis},{buzzwords_file}"
    settings_mq.send(settings_message.encode())
    settings_mq.close()

    card = create_bingo_card(buzzwords, xaxis, yaxis)
    marks = [[False] * xaxis for _ in range(yaxis)]
    if xaxis == yaxis and (xaxis == 5 or xaxis == 7):
        middle = xaxis // 2
        marks[middle][middle] = True
    print_bingo_card(card, marks)

    parent_pid = os.getpid()

    # Kindprozesserstellung zur Überwachung der Nachrichtenwarteschlange für die Gewinnbenachrichtigung
    pid = os.fork()
    if pid == 0:
        receive_messages(result_mq, parent_pid, logger)

    # Elternprozess bzw. Hauptprozess führt Spiellogik aus
    newBuzzword= random.choice(buzzwords)

    while True:
        console.print("Geben Sie ein Buzzword ein, um es zu markieren oder 'r', um die Markierung eines Feldes aufzuheben:")
        console.print(f"Neues Buzzword: [bold blue]{newBuzzword}[/bold blue]")
        buzzword = input()

        if buzzword.lower() == "r":
            buzzword = input("Geben Sie das Buzzword ein, dessen Markierung Sie aufheben möchten: ")
            for y, row in enumerate(card):
                for x, word in enumerate(row):
                    if word == buzzword:
                        marks[y][x] = False
                        logger.info(f"{buzzword} demarkiert ({x+1}/{y+1})")
            print_bingo_card(card, marks)
            continue
        
        for y, row in enumerate(card):
            for x, word in enumerate(row):
                if word == buzzword:
                    marks[y][x] = True
                    logger.info(f"{buzzword} markiert ({x+1}/{y+1})")
        print_bingo_card(card, marks)
        newBuzzword= random.choice(buzzwords)

        if check_winner(marks):
            os.kill(pid, signal.SIGTERM)
            logger.info("Sieg")
            console.print("[bold yellow]Bingo! Sie haben gewonnen![/bold yellow]")
            result_mq.send(f"{name} gewinnt!".encode())
            result_mq.close()    
            logger.info("Ende des Spiels")
            os._exit(0)

# Funktion zum Beitreten des Spiels und zum Starten des zweiten Spielerprozesses
@app.command()
def join():

    name = input("Geben Sie Ihren Namen ein: ")
    player_number = 2

    # Prüfen, ob die Nachrichtenwarteschlangen vom Host erstellt wurden bzw. ob das Spiel gestartet wurde
    try:
        settings_mq = MessageQueue(settings_queue_name, flags=O_RDWR)
        result_mq = MessageQueue(result_queue_name, flags=O_RDWR)
        console.print("Spiel beigetreten")
        console.print(f"Spieler: [bold yellow]{name}[/bold yellow]")

    except ExistentialError:
        console.print("Kein laufendes Spiel gefunden.")
        return
    
    # Empfangen der Spieleinstellungen vom Host
    settings_message, _ = settings_mq.receive()
    settings = settings_message.decode().split(',')
    xaxis, yaxis = int(settings[0]), int(settings[1])
    buzzwords_file = settings[2]

    # Schließen und Löschen der settings_mq nach Empfangen der Spieleinstellungen
    settings_mq.close()
    settings_mq.unlink()
    
    buzzwords = load_buzzwords(buzzwords_file)

    # Start des Loggers
    logger = setup_logger(player_number)

    logger.info("Start des Spiels")
    logger.info(f"Größe des Spielfelds: ({xaxis}/{yaxis})")

    card = create_bingo_card(buzzwords, xaxis, yaxis)
    marks = [[False] * xaxis for _ in range(yaxis)]
    if xaxis == yaxis and (xaxis == 5 or xaxis == 7):
        middle = xaxis // 2
        marks[middle][middle] = True
    print_bingo_card(card, marks)

    parent_pid = os.getpid()

    # Kindprozesserstellung zur Überwachung der Nachrichtenwarteschlange für die Gewinnbenachrichtigung
    pid = os.fork()
    if pid == 0:
        receive_messages(result_mq, parent_pid, logger)

    # Elternprozess bzw. Hauptprozess führt Spiellogik aus
    newBuzzword= random.choice(buzzwords)

    while True:
        console.print("Geben Sie ein Buzzword ein, um es zu markieren oder 'r', um die Markierung eines Feldes aufzuheben:")
        console.print(f"Neues Buzzword: [bold blue]{newBuzzword}[/bold blue]")
        buzzword = input()

        if buzzword.lower() == "r":
            buzzword = input("Geben Sie das Buzzword ein, dessen Markierung Sie aufheben möchten: ")
            for y, row in enumerate(card):
                for x, word in enumerate(row):
                    if word == buzzword:
                        marks[y][x] = False
                        logger.info(f"{buzzword} demarkiert ({x+1}/{y+1})")
            print_bingo_card(card, marks)
            continue
        
        for y, row in enumerate(card):
            for x, word in enumerate(row):
                if word == buzzword:
                    marks[y][x] = True
                    logger.info(f"{buzzword} markiert ({x+1}/{y+1})")
        print_bingo_card(card, marks)
        newBuzzword= random.choice(buzzwords)

        if check_winner(marks):
            os.kill(pid, signal.SIGTERM)
            logger.info("Sieg")
            console.print("[bold yellow]Bingo! Sie haben gewonnen![/bold yellow]")
            result_mq.send(f"{name} gewinnt!".encode())
            result_mq.close()
            logger.info("Ende des Spiels")
            os._exit(0)

if __name__ == "__main__":
    app()
