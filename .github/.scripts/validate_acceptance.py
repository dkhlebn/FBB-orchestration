#!/usr/bin/env python3
import os
import re
import sys
import yaml
from pathlib import Path
import subprocess


REFERENCE_AGREEMENT = """Я подтверждаю следующее:
1. Я не буду списывать решения у других участников курса.
2. При использовании больших языковых моделей (LLM) или других генеративных ИИ-инструментов
   для выполнения домашних заданий я обязуюсь полностью понимать присланный код и быть
   готовым пояснить, как он работает, почему используется та или иная конструкция,
   а также внести в него изменения по запросу преподавателя.

Нарушение этих правил может повлечь за собой исключение из курса или
аннулирование результатов.
"""

def normalize(s):
    return "\n".join(line.rstrip() for line in s.strip().splitlines())


def load_env_vars():
    return {
        'pr_title': os.environ.get('PR_TITLE', '').strip(),
        'pr_branch': os.environ.get('PR_HEAD_REF', '').strip(),
        'pr_author': os.environ.get('PR_AUTHOR', '').strip(),
        'base_sha': os.environ.get('BASE_SHA', '').strip(),
        'head_sha': os.environ.get('HEAD_SHA', '').strip(),
    }


def print_header(pr_author):
    print("=" * 70)
    print("Валидация регистрации на курс FBB Orchestration 2025")
    print(f"\tАвтор PR (эталонный username): {pr_author}")
    print("=" * 70)
    print()


def validate_branch_name(pr_author, pr_branch):
    errors = []
    expected = f"{pr_author}_accept"
    if not re.fullmatch(rf"{re.escape(pr_author)}_accept", pr_branch):
        errors.append(
            f"!!  Неверное имя ветки.\n"
            f"    Ожидается: '{expected}'\n"
            f"    Получено:  '{pr_branch}'\n"
        )
    else:
        print(f"....Ветка имеет корректное имя: {pr_branch}")
    return errors


def validate_pr_title(pr_author, pr_title):
    errors = []
    expected = f"acceptance-orch2025-{pr_author}"
    if pr_title != expected:
        errors.append(
            f"!!  Неверный заголовок pull request.\n"
            f"    Ожидается: '{expected}'\n"
            f"    Получено:  '{pr_title}'\n"
        )
    else:
        print(f"....Заголовок PR корректный: {pr_title}")
    return errors


def validate_file_exists(pr_author, head_sha):
    errors = []
    yaml_path = f'accepts_2025/{pr_author}.yaml'

    result = subprocess.run(
        ['git', 'cat-file', '-e', f'{head_sha}:{yaml_path}'],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        errors.append(
            f"!!  Файл не найден.\n"
            f"    Ожидаемый путь: '{yaml_path}'\n"
            f"    Убедитесь, что файл создан в правильной папке и имеет правильное имя."
        )
        return errors, None

    print(f"....Файл найден: {yaml_path}")
    return errors, yaml_path

def validate_yaml_content(pr_author, yaml_path, head_sha):
    errors = []

    try:
        result = subprocess.run(
            ['git', 'show', f'{head_sha}:{yaml_path}'],
            capture_output=True,
            text=True,
            check=True,
        )

        data = yaml.safe_load(result.stdout)

        if data is None:
            errors.append(
                f"!!  Файл '{yaml_path}' пустой или содержит только комментарии"
            )
            return errors

        required_fields = ['github_username', 'first_name', 'last_name',
                           'repo', 'grading', 'agreement', 'agree_to_rules']
        for field in required_fields:
            if field not in data:
                errors.append(f"!!  В файле отсутствует обязательное поле: '{field}'")
        if 'github_username' in data:
            if not isinstance(data['github_username'], str) or not data['github_username'].strip():
                errors.append("!!  Поле 'github_username' должно быть непустой строкой")
            elif data['github_username'] != pr_author:
                errors.append(
                    f"!!  Несоответствие github_username.\n"
                    f"    Указано: '{data['github_username']}'\n"
                    f"    Ожидается: '{pr_author}' (ваш GitHub username)"
                )
            else:
                print(f"....github_username совпадает с логином автора PR: {pr_author}")
        if 'first_name' in data:
            if not isinstance(data['first_name'], str) or not data['first_name'].strip():
                errors.append("!!  Поле 'first_name' должно быть непустой строкой с именем")
            else:
                print(f"....Имя указано: {data['first_name']}")
        if 'last_name' in data:
            if not isinstance(data['last_name'], str) or not data['last_name'].strip():
                errors.append("!!  Поле 'last_name' должно быть непустой строкой с фамилией")
            else:
                print(f"....Фамилия указана: {data['last_name']}")
        if 'repo' in data:
            repo_val = data['repo']
            if repo_val in ('None', None):
                print(f"....Выбран формат сдачи: проект (repo=None)")
            elif isinstance(repo_val, str) and repo_val.strip().startswith(('http://', 'https://')):
                print(f"....Указан репозиторий для домашних заданий: {repo_val.strip()}")
            else:
                errors.append(
                    f"!!  Поле 'repo' должно быть строкой 'None' или валидным URL (начинающимся с http:// или https://).\n"
                    f"    Получено: '{repo_val}' (тип: {type(repo_val).__name__})"
                )
        if 'grading' in data:
            if data['grading'] not in ['homeworks', 'project']:
                errors.append(
                    f"!!  Поле 'grading' должно быть 'homeworks' или 'project'.\n"
                    f"    Получено: '{data['grading']}'"
                )
            else:
                print(f"....Формат сдачи: {data['grading']}")

        if 'grading' in data and 'repo' in data:
            grading = data['grading']
            repo = data['repo']

            if grading == 'project' and repo not in ('None', None):
                errors.append(
                    "!!  При grading: project поле repo должно быть 'None'."
                )

            if grading == 'homeworks':
                if not (isinstance(repo, str) and repo.startswith(('http://', 'https://'))):
                    errors.append(
                        "!!  При grading: homeworks поле repo должно содержать URL репозитория."
                    )

        if 'agreement' in data:
            if not isinstance(data['agreement'], str) or not data['agreement'].strip():
                errors.append("!!  Поле 'agreement' должно содержать текст соглашения")
            else:
                if normalize(data['agreement']) != normalize(REFERENCE_AGREEMENT):
                    errors.append(
                        "!!  Текст соглашения не совпадает с официальным текстом курса.\n"
                        "    Скопируйте текст соглашения дословно из файла README.md в папке accepts_2025/"
                    )
                else:
                    print("....Текст соглашения совпадает с официальным текстом курса")
        if 'agree_to_rules' in data:
            if data['agree_to_rules'] not in ('yes', True):
                errors.append(
                    f"!!  Поле 'agree_to_rules' должно содержать значение 'yes'.\n"
                    f"    Получено: '{data['agree_to_rules']}'"
                )
            else:
                print("....Согласие с правилами подтверждено (agree_to_rules: yes)")
    except Exception as e:
        errors.append(f"!!  Ошибка с YAML-файлом: {e}")
    return errors


def validate_changed_files(pr_author, base_sha, head_sha):
    errors = []
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-status', base_sha, head_sha],
            capture_output=True,
            text=True,
            check=True,
        )
        changes = [line.split() for line in result.stdout.splitlines()]

        if len(changes) != 1:
            errors.append(
                f"!!  PR должен содержать ровно один изменённый файл.\n"
                f"    Обнаружено изменений: {len(changes)}"
            )
            return errors

        status, path = changes[0]
        expected = f'accepts_2025/{pr_author}.yaml'

        if status != 'A':
            errors.append(
                f"!!  Файл должен быть *добавлен*, а не изменён или удалён.\n"
                f"    Получено: {status} {path}"
            )

        if path != expected:
            errors.append(
                f"!!  Неверное имя файла.\n"
                f"    Ожидается: {expected}\n"
                f"    Получено:  {path}"
            )
        else:
            print(f"....Добавлен корректный файл: {path}")
        return errors
    except subprocess.CalledProcessError as e:
        errors.append(f"!!  Ошибка git diff: {e}")
        return errors



def print_results(errors):
    print("=" * 70)
    if errors:
        print("ОБНАРУЖЕНЫ ОШИБКИ (требуют исправления):")
        print()
        for err in errors:
            print(err)
            print()
    else:
        print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print()
    print("=" * 70)


def main():
    env = load_env_vars()
    print_header(env['pr_author'])
    all_errors = []
    all_errors.extend(validate_branch_name(env['pr_author'], env['pr_branch']))
    print()
    all_errors.extend(validate_pr_title(env['pr_author'], env['pr_title']))
    print()
    file_errors, yaml_path = validate_file_exists(env['pr_author'], env['head_sha'])
    all_errors.extend(file_errors)
    print()
    if yaml_path:
        content_errors = validate_yaml_content(env['pr_author'], yaml_path, env['head_sha'])
        all_errors.extend(content_errors)
        print()
    changed_errors = validate_changed_files(
        env['pr_author'], env['base_sha'], env['head_sha']
    )
    all_errors.extend(changed_errors)
    print_results(all_errors)
    sys.exit(0 if not all_errors else 1)


if __name__ == '__main__':
    main()
