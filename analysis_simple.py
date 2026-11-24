import csv
from datetime import datetime
from collections import defaultdict

def parse_timestamp(ts_str):
    """Парсит ISO timestamp, отбрасывая часовой пояс (все события в UTC+03:00)."""
    return datetime.fromisoformat(ts_str.split('+')[0].split('Z')[0])

def main():
    print("1. Загрузка данных...")
    data = []
    with open('students.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['Timestamp'] = parse_timestamp(row['Timestamp'])
            row['EventIndex'] = int(row['EventIndex'])
            data.append(row)

    # Группируем по процессам
    processes = defaultdict(list)
    for row in data:
        processes[row['ProcessInstanceId']].append(row)

    # Сортируем внутри каждого процесса по EventIndex
    for pid in processes:
        processes[pid].sort(key=lambda x: x['EventIndex'])

    print(f"   Загружено {len(data)} событий по {len(processes)} процессам.")

    anomalies = []

    # === АНОМАЛИЯ 1: Нарушение разделения ролей ===
    print("2. Поиск аномалий...")
    for pid, events in processes.items():
        for event in events:
            if (event['ActivityName'] == 'Согласование руководителем' and
                event['EventType'] == 'task_completed' and
                event['Role'] == 'requester'):
                anomalies.append({
                    'ProcessInstanceId': pid,
                    'AnomalyType': 'Нарушение разделения ролей',
                    'Explanation': 'Этап "Согласование руководителем" закрыт пользователем с ролью requester. Заявитель не должен согласовывать собственную заявку.'
                })
                break

    # === АНОМАЛИЯ 2: Бот-активность (<1 мин на согласование руководителя) ===
    for pid, events in processes.items():
        created = {}
        for event in events:
            if event['EventType'] == 'task_created':
                created[event['TaskId']] = event['Timestamp']
            elif event['EventType'] == 'task_completed' and event['TaskId'] in created:
                duration_min = (event['Timestamp'] - created[event['TaskId']]).total_seconds() / 60
                if event['ActivityName'] == 'Согласование руководителем' and duration_min < 1:
                    anomalies.append({
                        'ProcessInstanceId': pid,
                        'AnomalyType': 'Признаки автоматизированного согласования (бот)',
                        'Explanation': f'Длительность согласования руководителем: {duration_min:.1f} мин. Физически невозможно для ручной оценки и ознакомления с документами.'
                    })
                    break

    # === АНОМАЛИЯ 3: Пропуск обязательного этапа "Согласование руководителем" ===
    for pid, events in processes.items():
        # Проверяем, что процесс завершился как fulfilled
        final_result = None
        for event in events:
            if event['EventType'] == 'process_completed':
                final_result = event['Result']
                break
        if final_result != 'fulfilled':
            continue

        # Собираем все закрытые этапы
        completed_activities = set()
        for event in events:
            if event['EventType'] == 'task_completed':
                completed_activities.add(event['ActivityName'])

        # Проверяем наличие обязательного этапа
        if 'Согласование руководителем' not in completed_activities:
            anomalies.append({
                'ProcessInstanceId': pid,
                'AnomalyType': 'Пропуск обязательного этапа',
                'Explanation': 'Заявка успешно завершена (fulfilled), но полностью пропущен обязательный этап "Согласование руководителем". Маршрут пошел напрямую к бюджету.'
            })

    print(f"   Найдено {len(anomalies)} записей об аномалиях.")

    print("3. Сохранение результатов...")
    with open('anomalies.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['ProcessInstanceId', 'AnomalyType', 'Explanation'])
        writer.writeheader()
        writer.writerows(anomalies)

    print("   Файл 'anomalies.csv' успешно создан!")

if __name__ == "__main__":
    main()
