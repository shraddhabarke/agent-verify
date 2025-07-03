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





@mcp.tool()

def get_optimized_recipe_selection(query, criteria, min_rating=None, min_reviews=None, max_calories=None, max_prep_time=None):
    """
    Search for recipes matching a query and optimize the selection based on provided criteria.

    :param query: str, search query for the recipe.
    :param criteria: dict, contains filtering parameters such as 'servings', 'zucchini_included', etc.
    :param min_rating: float, optional, minimum star rating the recipe must have.
    :param min_reviews: int, optional, minimum number of reviews the recipe must have.
    :param max_calories: int, optional, maximum calories per serving.
    :param max_prep_time: int, optional, maximum total preparation time.
    :return: dict, the best-matching recipe with all relevant details or None if no match is found.
    """
    # Validate input types
    if not isinstance(query, str):
        raise ValueError("The 'query' parameter must be a string.")
    if not isinstance(criteria, dict):
        raise ValueError("The 'criteria' parameter must be a dictionary.")

    if min_rating is not None and not isinstance(min_rating, (int, float)):
        raise ValueError("The 'min_rating' parameter must be a number.")
    if min_reviews is not None and not isinstance(min_reviews, int):
        raise ValueError("The 'min_reviews' parameter must be an integer.")
    if max_calories is not None and not isinstance(max_calories, int):
        raise ValueError("The 'max_calories' parameter must be an integer.")
    if max_prep_time is not None and not isinstance(max_prep_time, int):
        raise ValueError("The 'max_prep_time' parameter must be an integer.")

    # Step 1: Search recipes using the query
    recipes = search(query)
    if not isinstance(recipes, list):
        raise ValueError("The 'search' function must return a list of recipes.")

    # Step 2: Filter recipes using the provided criteria
    filtered_recipes = filter_recipes_by_criteria(
        recipes=recipes,
        min_rating=min_rating,
        min_reviews=min_reviews,
        max_calories=max_calories,
        max_prep_time=max_prep_time
    )
    if not isinstance(filtered_recipes, list):
        raise ValueError("The 'filter_recipes_by_criteria' function must return a list of filtered recipes.")

    # Step 3: Iterate through filtered recipes to get detailed information and further validation
    for recipe in filtered_recipes:
        if not isinstance(recipe, dict) or 'URL' not in recipe:
            raise ValueError("Each recipe in the filtered list must be a dictionary with a 'URL' key.")
        
        recipe_details = get_recipe_details(recipe_url=recipe['URL'])
        if not isinstance(recipe_details, dict):
            raise ValueError("The 'get_recipe_details' function must return a dictionary of recipe details.")

        # Validate detailed criteria (if any specifics are passed in the criteria dictionary)
        if 'servings' in criteria:
            if not isinstance(criteria['servings'], int):
                raise ValueError("The 'servings' value in criteria must be an integer.")
            if recipe_details.get('servings', 0) < criteria['servings']:
                continue
        if 'zucchini_included' in criteria:
            if not isinstance(criteria['zucchini_included'], bool):
                raise ValueError("The 'zucchini_included' value in criteria must be a boolean.")
            if criteria['zucchini_included'] and 'zucchini' not in recipe_details.get('ingredients', []):
                continue
        
        # Return the first recipe that meets all criteria
        return recipe_details

    # If no recipe meets the criteria, return None
    return None
if __name__ == "__main__":

    mcp.run(transport='stdio')
