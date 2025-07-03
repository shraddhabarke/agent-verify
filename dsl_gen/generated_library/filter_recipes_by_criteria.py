import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import Any
# Current available functions
# Function search and get_recipe_details are defined as given

def search(query: str) -> Any:
    """Search for recipes by query string. Returns a list of recipes with title, URL, rating count, and rating value."""
    search_url = f'https://www.allrecipes.com/search?q={urllib.parse.quote_plus(query, safe="")}'

    response = requests.get(search_url)
    html_content = response.text
    result = _parse_search_result(html_content)
    return result

def get_recipe_details(recipe_url: str) -> Any:
    """Get detailed information for a recipe by URL. Returns a dictionary with title, rating, rating count, review count, description, prep time, cook time, total time, servings, yield, ingredients, nutrition facts, and directions."""
    response = requests.get(recipe_url)
    html_content = response.text
    return _parse_recipe_details(html_content)

def _parse_search_result(html_string) -> Any:
    soup = BeautifulSoup(html_string, 'html.parser')
    recipes = []

    # Find all recipe cards
    recipe_cards = soup.find_all(class_='mntl-card-list-card--extendable')

    for card in recipe_cards:
        url = card['href']

        t = card.find(class_='card__title')
        title = t.text.strip() if t else None

        t = card.select_one('.mntl-recipe-card-meta__rating-count-number')
        if t:
            rating_count_text = t.contents[0].strip()
            #rating_count = int(rating_count_text)
            rating_count = rating_count_text
        else:
            rating_count = 0

        stars = card.select('.mntl-recipe-star-rating svg')
        if stars:
            full_stars = sum(1 for star in stars if 'icon-star' in star['class'] and 'icon-star-half' not in star['class'])
            half_stars = sum(1 for star in stars if 'icon-star-half' in star['class'])
            rating = full_stars + 0.5 * half_stars
        else:
            rating = 0.0

        recipes.append({
            'title': title,
            'url': url,
            'rating_count': rating_count,
            'rating_value': rating,
        })

    return recipes

def _parse_recipe_details(html_content) -> Any:
    soup = BeautifulSoup(html_content, 'html.parser')

    recipe = {}

    title_tag = soup.find('h1', class_='article-heading')
    recipe['title'] = title_tag.get_text(strip=True) if title_tag else None

    rating_tag = soup.find('div', class_='mm-recipes-review-bar__rating')
    #recipe['rating'] = float(rating_tag.get_text(strip=True)) if rating_tag else None
    recipe['rating'] = rating_tag.get_text(strip=True) if rating_tag else None

    rating_count_tag = soup.find('div', class_='mm-recipes-review-bar__rating-count')
    #recipe['rating_count'] = int(rating_count_tag.get_text(strip=True).strip('()')) if rating_count_tag else None
    recipe['rating_count'] = rating_count_tag.get_text(strip=True).strip('()') if rating_count_tag else None

    review_count_tag = soup.find('div', class_='mm-recipes-review-bar__comment-count')
    #recipe['review_count'] = int(review_count_tag.get_text(strip=True).split()[0]) if review_count_tag else None
    recipe['review_count'] = review_count_tag.get_text(strip=True).split()[0] if review_count_tag else None

    # Extract description
    description_tag = soup.find('p', class_='article-subheading')
    recipe['description'] = description_tag.get_text(strip=True) if description_tag else None

    label_map = {
        'Prep Time': 'prep_time',
        'Cook Time': 'cook_time',
        'Total Time': 'total_time',
        'Servings': 'servings',
        'Yield': 'yield'
    }

    items = soup.find_all('div', class_='mm-recipes-details__item')
    for item in items:
        label = item.find('div', class_='mm-recipes-details__label').get_text(strip=True).rstrip(':')
        value = item.find('div', class_='mm-recipes-details__value').get_text(strip=True)
        if label in label_map:
            recipe[label_map[label]] = value

    ingredients = []
    ingredient_items = soup.find_all('li', class_='mm-recipes-structured-ingredients__list-item')
    for item in ingredient_items:
        quantity = item.find('span', attrs={'data-ingredient-quantity': True})
        unit = item.find('span', attrs={'data-ingredient-unit': True})
        name = item.find('span', attrs={'data-ingredient-name': True})

        ingredient = {
            'quantity': quantity.get_text(strip=True) if quantity else '',
            'unit': unit.get_text(strip=True) if unit else '',
            'name': name.get_text(strip=True) if name else ''
        }
        ingredients.append(ingredient)

    recipe['ingredients'] = ingredients

    rows = soup.select('tr.mm-recipes-nutrition-facts-summary__table-row')

    nutrition_facts = {}
    for row in rows:
        cells = row.find_all('td')
        if len(cells) == 2:
            value = cells[0].get_text(strip=True)
            nutrient = cells[1].get_text(strip=True)
            nutrition_facts[nutrient] = value
    recipe['nutrition_facts'] = nutrition_facts

    # Find all list items within the ordered list
    directions_section = soup.find(id='mm-recipes-steps_1-0')
    steps = directions_section.find_all('li') if directions_section else []

    # Extract text from each step
    step_texts = [step.get_text(strip=True) for step in steps]
    recipe['directions'] = step_texts

    return recipe

def filter_recipes_by_criteria(recipes, min_rating=None, min_reviews=None, max_calories=None, max_prep_time=None):
    """
    Filters a list of recipes based on provided criteria.
    
    :param recipes: List of dictionaries with recipe information.
    :param min_rating: (float, optional) Minimum rating a recipe must have. Default is None.
    :param min_reviews: (int, optional) Minimum number of reviews a recipe must have. Default is None.
    :param max_calories: (int, optional) Maximum calories per serving a recipe can have. Default is None.
    :param max_prep_time: (int, optional) Maximum preparation time (in minutes) a recipe can have. Default is None.
    :return: List of recipes that match all given criteria.
    """
    filtered_recipes = []
    
    for recipe in recipes:
        # Extract detailed information for the given recipe URL
        details = get_recipe_details(recipe['url'])
        
        # Apply filters one by one
        if min_rating is not None and details['rating'] < min_rating:
            continue
        if min_reviews is not None and details['rating_count'] < min_reviews:
            continue
        if max_calories is not None and 'calories' in details['nutrition_facts']:
            calories = details['nutrition_facts']['calories']
            if calories > max_calories:
                continue
        if max_prep_time is not None and details['prep_time'] > max_prep_time:
            continue
        
        # If the recipe passes all filters, include it in the results
        filtered_recipes.append(details)
    
    return filtered_recipes

# Unit tests
def test_filter_recipes_by_criteria():
    # Mocking the `search` results
    recipes = [
        {'url': 'https://www.allrecipes.com/recipe/21090/vegetarian-four-cheese-lasagna/'},
        {'url': 'https://www.allrecipes.com/recipe/229764/easy-vegetarian-spinach-lasagna/'},
        {'url': 'https://www.allrecipes.com/recipe/236878/debbies-vegetable-lasagna/'}
    ]
    
    # Mocking `get_recipe_details` for each recipe
    def mock_get_recipe_details(recipe_url):
        # Hardcoding mock details for these URLs
        mock_data = {
            'https://www.allrecipes.com/recipe/21090/vegetarian-four-cheese-lasagna/': {
                'rating': 4.5,
                'rating_count': 200,
                'prep_time': 20,
                'nutrition_facts': {'calories': 500},
            },
            'https://www.allrecipes.com/recipe/229764/easy-vegetarian-spinach-lasagna/': {
                'rating': 4.6,
                'rating_count': 150,
                'prep_time': 15,
                'nutrition_facts': {'calories': 400},
            },
            'https://www.allrecipes.com/recipe/236878/debbies-vegetable-lasagna/': {
                'rating': 4.2,
                'rating_count': 60,
                'prep_time': 45,
                'nutrition_facts': {'calories': 700},
            }
        }
        return mock_data.get(recipe_url, {})
    
    # Patch the `get_recipe_details` function
    global get_recipe_details
    original_get_recipe_details = get_recipe_details
    get_recipe_details = mock_get_recipe_details
    
    try:
        # Test 1: Filter by minimum rating only
        result = filter_recipes_by_criteria(recipes, min_rating=4.5)
        assert len(result) == 2  # Two recipes meet the rating criteria

        # Test 2: Filter by minimum reviews and maximum calories
        result = filter_recipes_by_criteria(recipes, min_reviews=100, max_calories=450)
        assert len(result) == 1  # Only one recipe meets the criteria
        
        # Test 3: Filter by maximum prep time
        result = filter_recipes_by_criteria(recipes, max_prep_time=30)
        assert len(result) == 2  # Two recipes meet the prep time criteria

        # Test 4: No recipe matches criteria
        result = filter_recipes_by_criteria(recipes, max_prep_time=10)
        assert len(result) == 0  # No recipe meets the criteria
        
        print("All tests passed!")
    finally:
        # Restore the original function
        get_recipe_details = original_get_recipe_details

# Run the tests
if __name__ == "__main__":
    test_filter_recipes_by_criteria()