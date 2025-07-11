from bs4 import BeautifulSoup
import requests
import urllib.parse
from mcp.server.fastmcp import FastMCP
from typing import Any
from typing import List, Union, Optional

# MCP server for AllRecipes.com
mcp = FastMCP('Recipe MCP server')

@mcp.tool()
def search(query: str) -> Any:
    """Search for recipes by query string. Returns a list of recipes with title, URL, rating count, and rating value."""
    search_url = f'https://www.allrecipes.com/search?q={urllib.parse.quote_plus(query, safe="")}'

    response = requests.get(search_url)
    html_content = response.text
    result = _parse_search_result(html_content)
    return result

@mcp.tool()
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


@mcp.tool()
def filter_recipes(recipe_list_string: Any, min_rating: str = None, min_reviews: str = None, max_calories: str = None, max_prep_time_mins: str = None, required_ingredient: str = None, exact_servings: str = None) -> str:
    import json
    from datetime import timedelta
    
    # print(f"[DEBUG] Entered filter_recipes. Argument types: recipe_list_string={type(recipe_list_string)}, min_rating={type(min_rating)}, min_reviews={type(min_reviews)}, max_calories={type(max_calories)}, max_prep_time_mins={type(max_prep_time_mins)}, required_ingredient={type(required_ingredient)}, exact_servings={type(exact_servings)}")
    
    def time_to_minutes(time_str):
        if not time_str or not isinstance(time_str, str): return 0
        total = 0
        time_str = time_str.lower()
        try:
            if 'hr' in time_str:
                hr_part = time_str.split('hr')[0].strip()
                total += int(hr_part) * 60
                if 'min' in time_str:
                    min_part = time_str.split('hr')[1].split('min')[0]
                    min_digits = ''.join([c for c in min_part if c.isdigit()])
                    if min_digits:
                        total += int(min_digits)
            elif 'min' in time_str:
                min_part = time_str.split('min')[0]
                min_digits = ''.join([c for c in min_part if c.isdigit()])
                if min_digits:
                    total += int(min_digits)
            else:
                min_digits = ''.join([c for c in time_str if c.isdigit()])
                if min_digits:
                    total += int(min_digits)
        except Exception as e:
            print(f"[ERROR] Failed to convert time string to minutes for '{time_str}': {e}")
            pass
        return total

    # Attempt to handle agent mistakes and convert input types
    try:
        if not isinstance(recipe_list_string, str):
            recipe_list_string = json.dumps(recipe_list_string)
    except Exception as e:
        return json.dumps({"error": f"[ERROR] Could not parse 'recipe_list_string': {str(e)}"})

    def try_float(val, default=0.0):
        try:
            return float(val)
        except Exception:
            return default

    def try_int(val, default=0):
        try:
            return int(str(val).replace(",", ""))
        except Exception:
            return default

    try:
        recipes = json.loads(recipe_list_string)
    except Exception as e:
        return json.dumps({"error": f"[ERROR] Could not JSON decode recipes: {str(e)}"})

    filtered = []
    for item in recipes:
        try:
            info = item.copy()
            # Apply filters from 'search' fields
            if min_rating is not None:
                mr = try_float(min_rating, None)
                recipe_rating = try_float(info.get('rating_value', 0), 0)
                if mr is not None and recipe_rating < mr:
                    continue
            if min_reviews is not None:
                mrw = try_int(min_reviews, None)
                rc = try_int(info.get('rating_count', 0), 0)
                if mrw is not None and rc < mrw:
                    continue
            # If full details are included, check more fields
            if 'ingredients' in info and required_ingredient is not None:
                ingredients_names = [i['name'].lower() for i in info['ingredients'] if 'name' in i and isinstance(i['name'], str)]
                if required_ingredient.lower() not in ' '.join(ingredients_names):
                    continue
            if 'nutrition_facts' in info and max_calories is not None:
                nf = info['nutrition_facts']
                cal = nf.get('Calories', None)
                mc = try_int(max_calories, None)
                if cal is not None:
                    # Handle various formats: e.g. '350 kcal', 350, etc
                    if isinstance(cal, str):
                        cal_val = try_int(cal.split()[0], None)
                    else:
                        cal_val = try_int(cal, None)
                    if mc is not None and cal_val is not None and cal_val > mc:
                        continue
            if max_prep_time_mins is not None:
                mptm = try_int(max_prep_time_mins, None)
                pt = info.get('prep_time')
                prep_minutes = time_to_minutes(pt)
                if mptm is not None and prep_minutes > mptm:
                    continue
            if exact_servings is not None:
                s = str(info.get('servings', '')).strip()
                es = str(exact_servings).strip()
                if s != es:
                    continue
            filtered.append(info)
        except Exception as e:
            print(f"[ERROR] Exception while filtering recipe: {e}")
            continue
    return json.dumps(filtered)



if __name__ == "__main__":
    mcp.run(transport='stdio')