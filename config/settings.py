def __post_init__(self):
    """Загрузка вопросов после инициализации"""
    config_dir = Path(__file__).parent
    json_path = config_dir / 'questions.json'
    
    if not json_path.exists():
        print(f"❌ Файл questions.json не найден в {config_dir}")
        print(f"   Проверьте наличие файла и его содержимое")
        self.questions = []
        self.niche_categories = []
        return
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.questions = data.get('questions', [])
        self.question_categories = data.get('categories', {})
        
        # Преобразуем категории ниш
        niche_categories_data = data.get('niche_categories', [])
        self.niche_categories = []
        
        for category_data in niche_categories_data:
            try:
                category = NicheCategory(
                    id=category_data['id'],
                    name=category_data['name'],
                    description=category_data.get('description', ''),
                    emoji=category_data.get('emoji', '📊')
                )
                self.niche_categories.append(category)
            except (KeyError, ValueError) as e:
                print(f"⚠️ Ошибка загрузки категории: {e}")
        
        print(f"✅ Конфигурация загружена из JSON файла")
        print(f"   📋 Вопросов: {len(self.questions)}")
        print(f"   📊 Категорий ниш: {len(self.niche_categories)}")
        
        # ДЕБАГ: выводим первые 2 вопроса для проверки
        for i, q in enumerate(self.questions[:2]):
            print(f"   Вопрос {i+1}: {q.get('id', 'no-id')} - {q.get('text', 'no-text')[:50]}...")
            
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка чтения JSON: {e}")
        self.questions = []
        self.niche_categories = []