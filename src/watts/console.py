import click
from prettytable import PrettyTable

from . import Database


@click.group()
def main():
    pass


@click.command
def results():
    db = Database()
    table = PrettyTable(field_names=['INDEX', 'PLUGIN', 'NAME', 'TIME'], align='l')
    for i, result in enumerate(db):
        table.add_row([i, result.plugin, result.name, result.time])
    click.echo(table.get_string())


@click.command
@click.argument('index', type=int)
def dir(index):
    db = Database()
    result = db[index]
    click.echo(result.base_path)


main.add_command(results)
main.add_command(dir)
