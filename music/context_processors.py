def gender_context(request):
    """
    Kontekst procesor dostarczający spersonalizowane końcówki i zwroty 
    w zależności od wybranej płci użytkownika.
    """
    if not request.user.is_authenticated:
        return {}
    
    try:
        gender = request.user.profile.gender
    except:
        gender = 'O'
        
    # Słownik zwrotów spersonalizowanych
    # M = Mężczyzna, F = Kobieta, O = Neutralny/Inna
    g = {
        'zostales': 'zostałeś' if gender == 'M' else 'zostałaś' if gender == 'F' else 'zostałeś/aś',
        'polubiles': 'polubiłeś' if gender == 'M' else 'polubiłaś' if gender == 'F' else 'polubiłeś/aś',
        'obserwowales': 'obserwowałeś' if gender == 'M' else 'obserwowałaś' if gender == 'F' else 'obserwowałeś/aś',
        'przesluchales': 'przesłuchałeś' if gender == 'M' else 'przesłuchałaś' if gender == 'F' else 'przesłuchałeś/aś',
        'odkryles': 'odkryłeś' if gender == 'M' else 'odkryłaś' if gender == 'F' else 'odkryłeś/aś',
        'twoj': 'Twój' if gender == 'M' else 'Twoja' if gender == 'F' else 'Twój/a',
        'twoim': 'Twoim' if gender == 'M' else 'Twoją' if gender == 'F' else 'Twoim/a',
        'stworzyles': 'stworzyłeś' if gender == 'M' else 'stworzyłaś' if gender == 'F' else 'stworzyłeś/aś',
        'dolaczyl': 'dołączył' if gender == 'M' else 'dołączyła' if gender == 'F' else 'dołączył/a',
        'zalogowany': 'zalogowany' if gender == 'M' else 'zalogowana' if gender == 'F' else 'zalogowany/a',
        'powrot': 'Wróciłeś' if gender == 'M' else 'Wróciłaś' if gender == 'F' else 'Wróciłeś/aś',
        'chetnie': 'chętnie' if gender == 'M' else 'chętnie' if gender == 'F' else 'chętnie', 
        'obserwowany': 'obserwowany' if gender == 'M' else 'obserwowana' if gender == 'F' else 'obserwowany/a',
        'widziany': 'widziany' if gender == 'M' else 'widziana' if gender == 'F' else 'widziany/a',
        'obserwujesz': 'obserwujesz' if gender == 'M' else 'obserwujesz' if gender == 'F' else 'obserwujesz',
        'obserwuj': 'obserwuj' if gender == 'M' else 'obserwuj' if gender == 'F' else 'obserwuj',
        'odobserwuj': 'odobserwuj' if gender == 'M' else 'odobserwuj' if gender == 'F' else 'odobserwuj',
        'polub': 'polub' if gender == 'M' else 'polub' if gender == 'F' else 'polub',
        'odlub': 'odlub' if gender == 'M' else 'odlub' if gender == 'F' else 'odlub',
        'przestan_obserwowac': 'przestań obserwować' if gender == 'M' else 'przestań obserwować' if gender == 'F' else 'przestań obserwować',
    }
    
    return {'g': g}
