# Code mit name, xaxis, yaxis Eingabe
import os
import random
import typer
from rich.console import Console
from rich.table import Table
from posix_ipc import MessageQueue, ExistentialError, O_CREAT, O_EXCL, O_RDWR

app = typer.Typer()
console = Console()

BUZZWORDS = [
    "Synergie", "Blockchain", "KI", "Big Data", "Cloud", "Agil", "IoT", "5G", "KPI", "Disruptiv",
    "Scrum", "DevOps", "Microservices", "Lean", "Kanban", "Paradigma", "Pivot", "Unicorn", "Innovativ", "Ecosystem",
    "Skalierbar", "On-Premises", "Container", "Serverless", "Low-Code"
]

message_queue_name = "/buzzword_bingo_queue"
msg_size = 1024

def create_bingo_card(xaxis: int, yaxis: int):
    selected_words = random.sample(BUZZWORDS, xaxis * yaxis)
    card = [selected_words[i:i + xaxis] for i in range(0, len(selected_words), xaxis)]
    return card

def print_bingo_card(card, marks):
    table = Table()
    for i in range(len(card[0])):
        table.add_column(str(i+1))

    for y, row in enumerate(card):
        table.add_row(*[f"[green]{word}[/green]" if marks[y][x] else word for x, word in enumerate(row)])
    
    console.print(table)

def check_winner(marks):
    size = len(marks)
    for i in range(size):
        if all(marks[i]) or all(row[i] for row in marks):
            return True
    if all(marks[i][i] for i in range(size)) or all(marks[i][size - 1 - i] for i in range(size)):
        return True
    return False

def receive_messages(mq):
    while True:
        msg, _ = mq.receive()
        message = msg.decode()
        if "gewinnt" in message:
            console.print(f"[bold red]{message}[/bold red]")
            mq.close()
            mq.unlink()
            os._exit(0)

@app.command()
def start():
    name = input("Geben Sie Ihren Namen ein: ")
    xaxis = int(input("Geben Sie die Anzahl der Spalten für die Bingo-Karte ein: "))
    yaxis = int(input("Geben Sie die Anzahl der Zeilen für die Bingo-Karte ein: "))

    try:
        mq = MessageQueue(message_queue_name, flags=O_CREAT | O_EXCL, mode=0o666, max_messages=10, max_message_size=msg_size)
        console.print("Spiel erstellt. Warten auf Spieler...")
    except ExistentialError:
        console.print("Spiel läuft bereits. Trete dem bestehenden Spiel bei.")
        return
    
    card = create_bingo_card(xaxis, yaxis)
    marks = [[False] * xaxis for _ in range(yaxis)]
    print_bingo_card(card, marks)

    pid = os.fork()
    if pid == 0:
        receive_messages(mq)

    while True:
        buzzword = input("Markiere ein Buzzword: ")
        for y, row in enumerate(card):
            for x, word in enumerate(row):
                if word == buzzword:
                    marks[y][x] = True
        print_bingo_card(card, marks)
        if check_winner(marks):
            console.print("[bold red]Bingo! Sie haben gewonnen![/bold red]")
            mq.send(f"{name} gewinnt!".encode())
            os._exit(0)

@app.command()
def join():
    name = input("Geben Sie Ihren Namen ein: ")

    try:
        mq = MessageQueue(message_queue_name, flags=O_RDWR)
    except ExistentialError:
        console.print("Kein laufendes Spiel gefunden.")
        return

    xaxis = int(input("Geben Sie die Anzahl der Spalten für die Bingo-Karte ein: "))
    yaxis = int(input("Geben Sie die Anzahl der Zeilen für die Bingo-Karte ein: "))
    card = create_bingo_card(xaxis, yaxis)
    marks = [[False] * xaxis for _ in range(yaxis)]
    print_bingo_card(card, marks)

    pid = os.fork()
    if pid == 0:
        receive_messages(mq)

    while True:
        buzzword = input("Markiere ein Buzzword: ")
        for y, row in enumerate(card):
            for x, word in enumerate(row):
                if word == buzzword:
                    marks[y][x] = True
        print_bingo_card(card, marks)
        if check_winner(marks):
            console.print("[bold red]Bingo! Sie haben gewonnen![/bold red]")
            mq.send(f"{name} gewinnt!".encode())
            os._exit(0)

if __name__ == "__main__":
    app()
