# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

import sys

import click
from prettytable import PrettyTable

from . import Database


@click.group()
def main():
    pass


@click.command()
@click.option('--job-id', default=None, type=int, help='Filter by job ID')
@click.option('--last-job', is_flag=True, help='Display most recent job')
@click.option('--plugin', default=None, help='Filter by plugin name')
@click.option('--name', default=None, help='Filter by name')
@click.option('--database', default=None, help='Path to database')
def results(job_id, last_job, plugin, name, database):
    """List results"""
    db = Database(database) if database else Database()
    table = PrettyTable(field_names=['Index', 'Job ID', 'Plugin', 'Name', 'Time'], align='l')

    # Determine most recent job
    if last_job:
        job_ids = set()
        for result in db:
            if result.job_id is not None:
                job_ids.add(result.job_id)
        if job_ids:
            job_id = max(job_ids)

    for i, result in enumerate(db):
        # Apply filters
        if job_id is not None and job_id != result.job_id:
            continue
        if plugin is not None and plugin != result.plugin:
            continue
        if name is not None and name != result.name:
            continue

        table.add_row([i, result.job_id, result.plugin, result.name, result.time])
    click.echo(table.get_string())


@click.command()
@click.option('--database', default=None, help='Path to database')
@click.argument('index', type=int)
def dir(database, index):
    """Show directory containing files for a specific result

    The 'index' can be determined from the Index column when running 'watts
    results'.

    """
    db = Database(database) if database else Database()
    try:
        result = db[index]
    except IndexError:
        click.echo(f"No result with index {index} in database at {db.path}", err=True)
        sys.exit(1)
    click.echo(result.base_path)


@click.command()
@click.option('--database', default=None, help='Path to database')
@click.argument('index', type=int)
def stdout(database, index):
    """Show standard output from a specific result

    The 'index' can be determined from the Index column when running 'watts
    results'.

    """
    db = Database(database) if database else Database()
    try:
        result = db[index]
    except IndexError:
        click.echo(f"No result with index {index} in database at {db.path}", err=True)
        sys.exit(1)
    click.echo(result.stdout)


@click.command()
@click.option('--database', default=None, help='Path to database')
@click.option('--all', is_flag=True, help='Remove all results')
@click.argument('index', type=int, required=False)
def rm(database, all, index):
    """Remove a result from the database

    The 'index' can be determined from the Index column when running 'watts
    results'. Note that removing a result will delete all input and output files
    associated with the result

    """
    db = Database(database) if database else Database()

    if not all and index is None:
        click.echo("Must either provide index argument or --all flag.", err=True)
        sys.exit(1)

    if all:
        db.clear()
    else:
        try:
            result = db[index]
        except IndexError:
            click.echo(f"No result with index {index} in database at {db.path}", err=True)
            sys.exit(1)
        db.remove(result)


main.add_command(results)
main.add_command(dir)
main.add_command(stdout)
main.add_command(rm)
