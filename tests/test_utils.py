from app import format_difficulty

def test_format_difficulty():
    assert format_difficulty(1) == 'Легкая'
    assert format_difficulty('1') == 'Легкая'
    assert format_difficulty(2) == 'Средняя'
    assert format_difficulty('2') == 'Средняя'
    assert format_difficulty(3) == 'Сложная'
    assert format_difficulty('3') == 'Сложная'
    assert format_difficulty('Легкая') == 'Легкая'
    assert format_difficulty('не число') == 'не число'