from bs4 import BeautifulSoup
import requests
import urllib.parse
from mcp.server.fastmcp import FastMCP
from typing import Any

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
def filter_recipes(recipes, min_reviews=None, min_rating=None, max_prep_time=None, required_ingredients=None):
    """
    Filters a list of recipes based on specified criteria.

    Args:
        recipes (list): The list of recipes to filter, where each recipe is a dictionary containing details such as 
                        "rating_count", "rating_value", "prep_time", and "ingredients".
        min_reviews (int, optional): Minimum number of reviews a recipe must have. Defaults to None.
        min_rating (float, optional): Minimum rating a recipe must have. Defaults to None.
        max_prep_time (int, optional): Maximum preparation time in minutes. Defaults to None.
        required_ingredients (list, optional): List of ingredients that must be present in the recipe. Defaults to None.

    Returns:
        list: List of recipes that meet the filtering conditions, or an empty list if no recipes match or inputs are invalid.
    """

    def convert_time_to_minutes(time_str):
        """Helper function to convert a time string like '1 hr 15 mins' or '15 mins' to minutes."""
        if not time_str or not isinstance(time_str, str):
            return None
        time_units = {"hr": 60, "mins": 1}
        minutes = 0
        parts = time_str.split()
        for i, part in enumerate(parts):
            if part.isdigit():
                unit = parts[i + 1] if i + 1 < len(parts) else ""
                minutes += int(part) * time_units.get(unit, 0)
        return minutes

    # Validate and preprocess input arguments
    if not isinstance(recipes, list):
        return "Error: 'recipes' must be a list of dictionaries."
    if min_reviews is not None:
        try:
            min_reviews = int(min_reviews)
        except ValueError:
            return "Error: 'min_reviews' must be an integer."
    if min_rating is not None:
        try:
            min_rating = float(min_rating)
        except ValueError:
            return "Error: 'min_rating' must be a float."
    if max_prep_time is not None:
        try:
            max_prep_time = int(max_prep_time)
        except ValueError:
            return "Error: 'max_prep_time' must be an integer."
    if required_ingredients is not None:
        if not isinstance(required_ingredients, list):
            return "Error: 'required_ingredients' must be a list of strings."

    filtered_recipes = []
    for recipe in recipes:
        if not isinstance(recipe, dict):
            return "Error: Each recipe must be a dictionary."

        # Filter by minimum number of reviews
        try:
            if min_reviews is not None and recipe.get("rating_count", 0) < min_reviews:
                continue
        except (TypeError, ValueError):
            return "Error: 'rating_count' in a recipe must be an integer."

        # Filter by minimum rating
        try:
            if min_rating is not None and recipe.get("rating_value", 0) < min_rating:
                continue
        except (TypeError, ValueError):
            return "Error: 'rating_value' in a recipe must be a float."

        # Filter by maximum preparation time
        prep_time = convert_time_to_minutes(recipe.get("prep_time"))
        if max_prep_time is not None and (prep_time is None or prep_time > max_prep_time):
            continue

        # Filter by required ingredients
        if required_ingredients is not None:
            try:
                recipe_ingredients = [
                    ing.get("name", "").lower()
                    for ing in recipe.get("ingredients", [])
                    if isinstance(ing, dict)
                ]
                if not all(req_ing.lower() in recipe_ingredients for req_ing in required_ingredients):
                    continue
            except Exception:
                return "Error: 'ingredients' must be a list of dictionaries with a 'name' key."

        # If all conditions are met, include the recipe
        filtered_recipes.append(recipe)

    return filtered_recipes
if __name__ == "__main__":
    mcp.run(transport='stdio')
