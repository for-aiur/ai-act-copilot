"""Stateless jobs using real pipeline and test-only GitHub/model transports."""
import pytest

from aiact.github_bot.actions import run_event
from aiact.github_bot.github import BotError
from test_github_bot import system, payload, feedback


def test_separate_jobs_update_existing_comments_without_retained_database(system, tmp_path):
    config, store, github, service, contexts = system
    run_event(config, 'pull_request_target', payload(), github, tmp_path/'first', service.scanner)
    count = len(github.remote)
    assert count == 2
    assert 'Stateless PR review' in github.remote[0][1]['body']
    assert 'Decisions are recorded' not in github.remote[0][1]['body']
    run_event(config, 'pull_request_target', payload(), github, tmp_path/'second', service.scanner)
    assert len(github.remote) == count
    assert contexts == ['', '']


def test_rescan_requires_authorized_actor_and_exact_command(system, tmp_path):
    config, store, github, service, contexts = system
    event = feedback('a'*20, 'resolve', actor='dev')
    run_event(config, 'issue_comment', event, github, tmp_path/'ignored', service.scanner)
    assert not contexts
    event['comment']['body'] = '/aiact rescan'
    event['comment']['user']['login'] = 'outsider'
    run_event(config, 'issue_comment', event, github, tmp_path/'outsider', service.scanner)
    assert not contexts
    event['comment']['user']['login'] = 'dpo'
    run_event(config, 'issue_comment', event, github, tmp_path/'allowed', service.scanner)
    assert len(contexts) == 1


def test_actions_rejects_fork_and_wrong_repository(system, tmp_path):
    config, store, github, service, contexts = system
    github.fork = True
    with pytest.raises(BotError, match='fork_review_not_enabled'):
        run_event(config, 'pull_request_target', payload(), github, tmp_path/'fork', service.scanner)
    event = payload()
    event['repository']['full_name'] = 'other/repository'
    with pytest.raises(BotError, match='repository_not_allowed'):
        run_event(config, 'pull_request_target', event, github, tmp_path/'other', service.scanner)
