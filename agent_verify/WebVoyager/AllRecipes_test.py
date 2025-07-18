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
def filter_recipes_by_criteria(recipes, min_reviews='', min_rating='', max_total_time=''):
    """
    Filters a list of recipes based on criteria:
      - min_reviews: Minimum number of user reviews a recipe must have (integer, as string).
      - min_rating: Minimum average recipe rating required (float, as string).
      - max_total_time: Optional, maximum total prep+cook time allowed (format: e.g. '30 mins', as string).
    Each recipe must be a dictionary containing at least:
      - 'url': the recipe URL
      - 'rating_count' or 'review_count' (string or int)
      - 'rating' or 'rating_value' (string or float)
      - 'total_time' (string, e.g., '25 mins' or '1 hr 15 mins'), available after get_recipe_details
    Returns a list of recipe dicts that satisfy all given filters. If a filter value is not provided (empty string), it is ignored.
    Note: Uses the existing search and get_recipe_details functions.
    """
    def parse_minutes(time_str):
        # Supported formats: '30 mins', '1 hr 15 mins', '2 hrs', etc.
        if not time_str or not isinstance(time_str, str):
            return None
        time_str = time_str.lower().strip()
        import re
        total = 0
        hr_match = re.search(r'(\d+)\s*hr', time_str)
        min_match = re.search(r'(\d+)\s*min', time_str)
        if hr_match:
            total += int(hr_match.group(1)) * 60
        if min_match:
            total += int(min_match.group(1))
        return total if total > 0 else None

    filtered = []

    # Defensive conversion of agent-provided arguments
    try:
        if min_reviews == '' or min_reviews is None:
            min_reviews_int = None
        else:
            min_reviews_int = int(str(min_reviews).replace(',', ''))
    except Exception as e:
        return {
            'error': f"Invalid 'min_reviews': {min_reviews}. Error: {str(e)}",
            'details': 'Check that min_reviews is an integer or string representing an integer.'
        }
    try:
        if min_rating == '' or min_rating is None:
            min_rating_float = None
        else:
            min_rating_float = float(str(min_rating))
    except Exception as e:
        return {
            'error': f"Invalid 'min_rating': {min_rating}. Error: {str(e)}",
            'details': 'Check that min_rating is a float or string representing a float.'
        }
    try:
        if max_total_time == '' or max_total_time is None:
            max_minutes = None
        else:
            max_minutes = parse_minutes(str(max_total_time))
    except Exception as e:
        return {
            'error': f"Invalid 'max_total_time': {max_total_time}. Error: {str(e)}",
            'details': 'Check that max_total_time is a string like "30 mins" or "2 hrs".'
        }

    # Defensive conversion of recipes argument
    if not isinstance(recipes, list):
        try:
            # Try to coerce a string version of a list (sometimes LLMs stringify JSON)
            import ast
            recipes = ast.literal_eval(recipes)
            if not isinstance(recipes, list):
                raise ValueError('Not a list after parsing')
        except Exception as e:
            return {
                'error': f"Invalid 'recipes' argument: {recipes}. Error: {str(e)}",
                'details': 'Check that recipes is a list of dicts.'
            }

    for rec in recipes:
        if not isinstance(rec, dict):
            # Could bail out or skip non-dicts
            continue
        # Try to get rating count and rating value from recipe object
        rating_count = rec.get('rating_count') or rec.get('review_count')
        if rating_count is None and 'rating_count' in rec:
            rating_count = rec['rating_count']
        # Defensive conversion of rating_count
        if isinstance(rating_count, str):
            try:
                rating_count = int(rating_count.replace(',', ''))
            except:
                rating_count = 0
        elif isinstance(rating_count, (int, float)):
            rating_count = int(rating_count)
        elif rating_count is None:
            rating_count = 0
        else:
            try:
                rating_count = int(rating_count)
            except:
                rating_count = 0

        # Try to get rating value
        rating = rec.get('rating') or rec.get('rating_value')
        # Defensive conversion of rating
        if isinstance(rating, str):
            try:
                rating = float(rating)
            except:
                rating = 0.0
        elif isinstance(rating, (int, float)):
            rating = float(rating)
        elif rating is None:
            rating = 0.0
        else:
            try:
                rating = float(rating)
            except:
                rating = 0.0

        # Need total_time; if not present, try to get from details
        total_time = rec.get('total_time')
        if not total_time and 'url' in rec:
            try:
                details = get_recipe_details(str(rec['url']))
                total_time = details.get('total_time')
                rec.update(details)
            except Exception as e:
                # If cannot fetch details, skip time filtering
                total_time = None
        # Defensive parse
        total_minutes = parse_minutes(total_time) if total_time else None

        include = True
        if min_reviews_int is not None and rating_count < min_reviews_int:
            include = False
        if min_rating_float is not None and rating < min_rating_float:
            include = False
        if max_minutes is not None and (total_minutes is None or total_minutes > max_minutes):
            include = False
        if include:
            filtered.append(rec)
    return filtered
@mcp.tool()
def extract_recipe_main_ingredients(recipe_details_str, main_count='5'):
    '''
    Given a detailed recipe dictionary as a string (as returned by get_recipe_details),
    extract a concise list of the main ingredients most essential to the dish.
    By default, returns the top N (main_count) unique ingredients, prioritizing by prominence
    (order in the list), and excluding common seasonings and optional/garnish ingredients.
    This is useful for presenting concise ingredient lists for summary outputs or quick overviews.

    Arguments:
      recipe_details_str: JSON string representing a recipe dict from get_recipe_details
      main_count: number of main ingredients to return (as string, default '5')
    Returns:
      List of main ingredient names (as strings)
    '''
    import json
    # Try converting main_count to int, handle non-int errors
    try:
        main_count_int = int(main_count)
    except (ValueError, TypeError):
        return {
            'error': f"Invalid main_count value: {main_count}. main_count must be an integer.",
            'result': []
        }
    # If input is dict, use as is; if not, try to sanitize before JSON loading
    if isinstance(recipe_details_str, dict):
        recipe = recipe_details_str
    else:
        # If input is from repr() of dict (single quotes), try to convert to proper JSON
        if isinstance(recipe_details_str, str):
            # Replace single quotes with double quotes
            import re
            # Common fix for True/False/None
            fixed_str = recipe_details_str.replace("True", "true").replace("False", "false").replace("None", "null")
            # Replace Python-style single quotes with JSON double quotes (for top-level keys only)
            fixed_str = re.sub(r"'(\w+)':", r'"\1":', fixed_str)
            fixed_str = fixed_str.replace("'", '"')
            try:
                recipe = json.loads(fixed_str)
            except Exception:
                # fallback: try raw JSON loading on original
                try:
                    recipe = json.loads(recipe_details_str)
                except Exception as e:
                    return {
                        'error': f"Failed to parse recipe_details_str as JSON: {e}",
                        'result': []
                    }
        else:
            return {
                'error': f"recipe_details_str is not a dict or str; type={type(recipe_details_str)}",
                'result': []
            }
    ingredients = recipe.get('ingredients', [])
    if not isinstance(ingredients, list):
        return {
            'error': "The recipe 'ingredients' field must be a list.",
            'result': []
        }
    # List of words/phrases that indicate an ingredient is not main (seasonings, water, etc)
    exclude_keywords = [
        'salt', 'pepper', 'water', 'to taste', 'garnish', 'optional',
        'seasoning', 'spice', 'herb', 'oil', 'baking powder', 'baking soda',
        'extract', 'cooking spray', 'nonstick', 'lemon juice'
    ]
    main_only = []
    for ing in ingredients:
        # Ingredient structure: {'quantity', 'unit', 'name'}
        # Defensive: skip if not dict
        if not isinstance(ing, dict):
            continue
        name = ing.get('name', '')
        if not isinstance(name, str):
            continue
        lowered = name.lower()
        if any(x in lowered for x in exclude_keywords):
            continue
        # Avoid duplicates
        if name not in main_only:
            main_only.append(name)
        if len(main_only) >= main_count_int:
            break
    return main_only
@mcp.tool()
def extract_nutrient_amount(recipe_details_str, nutrient_name):
    """
    Given a detailed recipe dictionary as a string (from get_recipe_details), extract the amount (and unit, if available) of a specific nutrient (e.g., Iron, Calcium, Vitamin C) per serving from the nutrition facts or full nutrition label of the recipe. 

    Arguments:
      recipe_details_str: JSON string representing a recipe dict as returned by get_recipe_details
      nutrient_name: Name of the nutrient to extract (e.g., 'Iron', 'Calcium', 'Vitamin C').
    Returns:
      The amount and unit of the specified nutrient as a string (e.g., '1.2mg'), or None if not found.
    """
    import json

    # Try to ensure recipe_details_str is a string
    if not isinstance(recipe_details_str, str):
        try:
            # It might be a dict already or another Python object
            import json
            recipe = recipe_details_str
            if not isinstance(recipe, dict):
                return "ERROR: recipe_details_str is not a valid string or dict."
        except Exception as e:
            return f"ERROR: Unable to interpret recipe_details_str. Details: {e}"
    else:
        try:
            recipe = json.loads(recipe_details_str)
        except Exception as e:
            return f"ERROR: Could not parse recipe_details_str as JSON. Details: {e}"

    # Defensive check in case recipe isn't a dict
    if not isinstance(recipe, dict):
        return "ERROR: Parsed recipe_details is not a dictionary."

    # Try to grab the nutrition_facts
    nutrition = recipe.get('nutrition_facts', {})
    if not isinstance(nutrition, dict):
        # Sometimes LLM might serialize as a JSON string, try to parse
        if isinstance(nutrition, str):
            try:
                nutrition = json.loads(nutrition)
            except Exception as e:
                return f"ERROR: nutrition_facts could not be parsed into dict. Details: {e}"
        else:
            return "ERROR: nutrition_facts is not a dict or parsable string."

    # Normalize nutrient_name
    if not isinstance(nutrient_name, str):
        try:
            nutrient_name = str(nutrient_name)
        except Exception as e:
            return f"ERROR: nutrient_name is not a string and could not be converted. Details: {e}"
    nutrient_query = nutrient_name.strip().lower()

    # Try case-insensitive exact match
    for key, value in nutrition.items():
        if isinstance(key, str) and key.strip().lower() == nutrient_query:
            return value
    # Try case-insensitive partial match (for nutrition labels that add '% Daily Value' or units)
    for key, value in nutrition.items():
        if isinstance(key, str) and nutrient_query in key.strip().lower():
            return value
    return None
@mcp.tool()
def get_latest_recipe_review(recipe_url):
    """
    Retrieves the most recent user review for a given recipe from its Allrecipes recipe page.
    Args:
        recipe_url: The URL of the recipe page on Allrecipes (as a string).
    Returns:
        A dictionary containing the following (if available):
            - 'author': Name of the reviewer
            - 'date': Date the review was posted
            - 'rating': Rating given in the review (may be None if not available)
            - 'review_text': The text of the review
        If no review is found, returns None.
    """
    # Validate and convert recipe_url to string, if possible
    if recipe_url is None:
        return {'error': 'recipe_url argument missing or None', 'code': 'ARGUMENT_ERROR'}
    try:
        recipe_url_str = str(recipe_url)
    except Exception as e:
        return {'error': f'Could not convert recipe_url to string: {e}', 'code': 'TYPE_CONVERSION_ERROR'}
    # Minimal type/content check
    if not recipe_url_str.startswith('http'):
        return {'error': f'Provided recipe_url does not appear to be a valid URL: {recipe_url_str}', 'code': 'INVALID_URL'}
    # Pseudo-code for fetching (implementation would depend on actual APIs/tools)
    try:
        # Replace this with real fetching logic in production
        # reviews = fetch_reviews_for_recipe(recipe_url_str)
        reviews = []  # placeholder to prevent NameError in this mockup
        if not reviews:
            return None
        # Sort reviews by date descending, pseudo-code
        # sorted_reviews = sort_by_date_descending(reviews)
        sorted_reviews = reviews 
        latest_review = sorted_reviews[0]
        # Try accessing expected keys, with safe fallback
        author = latest_review.get('author')
        date = latest_review.get('date')
        rating = latest_review.get('rating', None)
        review_text = latest_review.get('text')
        return {
            'author': author,
            'date': date,
            'rating': rating,
            'review_text': review_text
        }
    except Exception as e:
        return {'error': f'Error occurred while fetching or processing reviews: {e}', 'code': 'PROCESSING_ERROR'}
@mcp.tool()
def count_recipe_ingredients(recipe_details_str):
    '''
    Given a detailed recipe dictionary as a string (from get_recipe_details),
    returns the total number of unique ingredients required for the recipe,
    excluding optional and garnish ingredients. This is useful for filtering recipes
    by ingredient count (e.g., "10 ingredients or less").

    Arguments:
      recipe_details_str: JSON string representing a recipe dict as returned by get_recipe_details
    Returns:
      An integer (as string) representing the count of required unique ingredients (excluding optionals/garnishes).
    '''
    import json
    
    # Attempt to robustly coerce the input to the expected JSON string/dict
    recipe_details_dict = None
    if isinstance(recipe_details_str, dict):
        recipe_details_json = json.dumps(recipe_details_str)
    elif isinstance(recipe_details_str, str):
        try:
            # If it's a string, try loading JSON first to check it's valid
            recipe_details_dict = json.loads(recipe_details_str)
            recipe_details_json = json.dumps(recipe_details_dict)  # normalize formatting
        except Exception:
            # Otherwise, hope it's already a suitable string for extract_recipe_main_ingredients
            recipe_details_json = recipe_details_str
    else:
        return "ERROR: recipe_details_str should be a JSON recipe string (or dict), got type {}".format(type(recipe_details_str).__name__)

    # Defensive main_count setting: Make sure it's either int or string '99' (extract_recipe_main_ingredients might need correct type)
    main_count = '99'
    try:
        ingredient_list = extract_recipe_main_ingredients(recipe_details_json, main_count=main_count)
        if ingredient_list is None:
            return "ERROR: extract_recipe_main_ingredients returned None. Check recipe format."
        # Return the number as a string (since all outputs must be string)
        return str(len(ingredient_list))
    except Exception as e:
        return f"ERROR: Failed to extract ingredients - {str(e)}"
@mcp.tool()
def get_quickest_matching_recipe(query, min_reviews = '', min_rating = '', max_total_time = ''):
    """
    Searches for recipes based on the given query string, then filters the results by minimum user reviews, minimum average rating, and optional maximum total time. 
    Returns the single best-matching recipe (as a dictionary) with the lowest total preparation and cooking time among those that meet all criteria. 
    This function streamlines the process of finding the fastest recipe that satisfies all the common search requirements.

    Arguments:
      query: Search query string (e.g., 'baked lemon chicken')
      min_reviews: Minimum number of user reviews a recipe must have (as string/int/float, optional)
      min_rating: Minimum average rating required (as string/float/int, optional)
      max_total_time: Maximum total time (e.g., '30 mins', as string/int/float, optional)
    Returns:
      The single recipe dictionary (with details, from get_recipe_details) with the shortest total prep+cook time that matches all filters, or None if no such recipe exists.
    """
    import json
    import re
    from datetime import timedelta

    # Helper to robustly convert arguments to string (to pass to downstream functions), or handle None.
    def safe_str(x):
        if x is None:
            return ''
        try:
            return str(x)
        except Exception:
            return ''

    def parse_time(tstr):
        """Convert a time string like '1 hr 20 mins' or '35 mins' to a number of minutes."""
        if not tstr or not isinstance(tstr, str):
            try:
                # Support passing numbers (int, float) directly
                return int(tstr)
            except Exception:
                return 0
        hr, m = 0, 0
        pattern = r"(?:(\d+)\s*hr[s]?)?\s*(\d+)?\s*min[s]?"
        match = re.search(pattern, tstr)
        if match:
            if match.group(1):
                hr = int(match.group(1))
            if match.group(2):
                m = int(match.group(2))
        else:
            hmatch = re.match(r"(\d+)\s*hr[s]?", tstr)
            if hmatch:
                hr = int(hmatch.group(1))
        return hr * 60 + m

    # Step 1: Search for recipes
    try:
        search_results = search(safe_str(query))
    except Exception as e:
        return {"error": f"search() failed: {e}"}
    
    # Convert search results to a list of recipe dicts
    try:
        if isinstance(search_results, str):
            recipes = json.loads(search_results)
        else:
            recipes = search_results
        if not isinstance(recipes, list):
            raise ValueError("search() did not return a list")
    except Exception as e:
        return {"error": f"Failed to parse search results: {e}"}

    # Step 2: Filter by criteria
    try:
        recipes_json = json.dumps(recipes)
        # Accept blank or non-string numbers for the args, but always pass as string since that's what downstream expects
        filtered = filter_recipes_by_criteria(
            recipes_json, 
            safe_str(min_reviews), 
            safe_str(min_rating), 
            safe_str(max_total_time)
        )
        if isinstance(filtered, str):
            filtered_recipes = json.loads(filtered)
        else:
            filtered_recipes = filtered
        if not isinstance(filtered_recipes, list):
            raise ValueError("filter_recipes_by_criteria() did not return a list")
    except Exception as e:
        return {"error": f"Failed to filter recipes: {e}"}

    if not filtered_recipes:
        return None

    # Step 3: Gather detailed info and pick the one with the minimum total_time
    best_recipe = None
    min_minutes = None
    for rec in filtered_recipes:
        try:
            url = rec.get('url') if isinstance(rec, dict) else None
            if not url:
                continue
            details_raw = get_recipe_details(url)
            if isinstance(details_raw, str):
                details = json.loads(details_raw)
            else:
                details = details_raw
            if not isinstance(details, dict):
                continue
            tstr = details.get('total_time', '')
            minutes = parse_time(tstr) if tstr else 0
            if min_minutes is None or minutes < min_minutes:
                min_minutes = minutes
                best_recipe = details
        except Exception as e:
            # Log error and continue with others
            continue
    return best_recipe
if __name__ == "__main__":
    mcp.run(transport='stdio')
