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
@mcp.tool()
def filter_recipes_by_nutrition(recipes, max_calories=None, max_fat=None, max_carbs=None, max_protein=None):
    """
    Filters a list of recipes based on specified nutritional criteria.

    Args:
        recipes (list): The list of recipes to filter, where each recipe is a dictionary containing "nutrition_facts".
        max_calories (float, optional): Maximum allowable calories per serving. Defaults to None.
        max_fat (float, optional): Maximum allowable fat per serving in grams. Defaults to None.
        max_carbs (float, optional): Maximum allowable carbohydrates per serving in grams. Defaults to None.
        max_protein (float, optional): Maximum allowable protein per serving in grams. Defaults to None.

    Returns:
        list: List of recipes that meet the nutritional constraints, or an empty list if no recipes match or inputs are invalid.
    """
    
    # Validate and normalize inputs
    try:
        max_calories = float(max_calories) if max_calories is not None else None
        max_fat = float(max_fat) if max_fat is not None else None
        max_carbs = float(max_carbs) if max_carbs is not None else None
        max_protein = float(max_protein) if max_protein is not None else None
    except (ValueError, TypeError):
        return []  # Return empty list if any of the thresholds are invalid

    filtered_results = []
    for recipe in recipes:
        try:
            if not isinstance(recipe, dict):
                continue  # Skip invalid recipe entries
            
            nutrition = recipe.get("nutrition_facts", {})
            
            # Ensure nutrition values are in the correct format
            calories = float(nutrition.get("Calories", 0))
            fat = float(str(nutrition.get("Fat", "0")).replace('g', '').strip())
            carbs = float(str(nutrition.get("Carbs", "0")).replace('g', '').strip())
            protein = float(str(nutrition.get("Protein", "0")).replace('g', '').strip())

            # Apply filters
            if max_calories is not None and calories > max_calories:
                continue
            if max_fat is not None and fat > max_fat:
                continue
            if max_carbs is not None and carbs > max_carbs:
                continue
            if max_protein is not None and protein > max_protein:
                continue
            
            filtered_results.append(recipe)
        except (ValueError, TypeError):
            continue  # Skip recipes with invalid nutrition data

    return filtered_results
@mcp.tool()
def format_recipe_details(recipe_details):
    """
    Formats a recipe's detailed information into a structured, user-friendly string or object.

    Args:
        recipe_details (dict): A dictionary with detailed information about the recipe. Contains keys such as 
                               `title`, `description`, `rating`, `rating_count`, `prep_time`, `cook_time`, 
                               `total_time`, `servings`, `ingredients`, `nutrition_facts`, and `directions`.

    Returns:
        str: A formatted string representing the recipe's details, including title, description, rating, 
             preparation times, ingredients, directions, and nutrition facts.
    """
    if not isinstance(recipe_details, dict):
        return "Error: recipe_details must be a dictionary."

    # Helper function to safely extract string values
    def safe_str(value, default="N/A"):
        return str(value) if value is not None else default

    # Helper function to ensure a list format
    def ensure_list(value):
        return value if isinstance(value, list) else []

    # Helper function to ensure a dictionary format
    def ensure_dict(value):
        return value if isinstance(value, dict) else {}

    # Extracting basic details
    title = safe_str(recipe_details.get('title', 'Title not available'))
    description = safe_str(recipe_details.get('description', 'No description available'))
    rating = safe_str(recipe_details.get('rating', 'N/A'))
    rating_count = safe_str(recipe_details.get('rating_count', '0'))
    prep_time = safe_str(recipe_details.get('prep_time', 'N/A'))
    cook_time = safe_str(recipe_details.get('cook_time', 'N/A'))
    total_time = safe_str(recipe_details.get('total_time', 'N/A'))
    servings = safe_str(recipe_details.get('servings', 'N/A'))
    
    # Formatting ingredients
    ingredients = ensure_list(recipe_details.get('ingredients', []))
    formatted_ingredients = "\n".join([
        f"- {safe_str(ingredient.get('quantity'))} {safe_str(ingredient.get('unit'))} {safe_str(ingredient.get('name', 'Unknown ingredient'))}"
        for ingredient in ingredients
        if isinstance(ingredient, dict)
    ]) or "No ingredients available"
    
    # Formatting directions
    directions = ensure_list(recipe_details.get('directions', []))
    formatted_directions = "\n".join([
        f"{idx + 1}. {safe_str(step)}" for idx, step in enumerate(directions)
    ]) or "No directions available"
    
    # Formatting nutrition facts
    nutrition_facts = ensure_dict(recipe_details.get('nutrition_facts', {}))
    formatted_nutrition = ", ".join([
        f"{safe_str(key)}: {safe_str(value)}" for key, value in nutrition_facts.items()
    ]) or "No nutrition facts available"
    
    # Combining all details
    formatted_recipe = (
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Rating: {rating} stars (based on {rating_count} reviews)\n"
        f"Preparation Time: {prep_time}\n"
        f"Cooking Time: {cook_time}\n"
        f"Total Time: {total_time}\n"
        f"Servings: {servings}\n\n"
        f"Ingredients:\n{formatted_ingredients}\n\n"
        f"Directions:\n{formatted_directions}\n\n"
        f"Nutrition Facts:\n{formatted_nutrition}"
    )

    return formatted_recipe
@mcp.tool()
def rank_recipes_by_popularity(recipes, rating_weight=0.7, review_weight=0.3):
    """
    Ranks a list of recipes by popularity using a weighted scoring system that takes into account
    both the average rating and the number of reviews. Recipes are sorted from most to least popular.

    Args:
        recipes (list): List of recipes, where each recipe is a dictionary containing "rating_value" 
                        and "rating_count".
        rating_weight (float): Weight assigned to the average rating in the popularity score (default: 0.7).
        review_weight (float): Weight assigned to the review count in the popularity score (default: 0.3).

    Returns:
        list: List of recipes sorted by popularity in descending order, or an empty list if input is invalid.
    """
    if not isinstance(recipes, list) or not all(isinstance(recipe, dict) for recipe in recipes):
        return "Error: 'recipes' must be a list of dictionaries."

    # Ensure weights are numbers
    try:
        rating_weight = float(rating_weight)
        review_weight = float(review_weight)
    except ValueError:
        return "Error: 'rating_weight' and 'review_weight' must be numeric values."

    def calculate_popularity(recipe):
        try:
            # Extract and convert rating and review values
            rating_value = float(recipe.get("rating_value", 0))
            rating_count = int(recipe.get("rating_count", 0))
            return (rating_weight * rating_value) + (review_weight * rating_count)
        except (ValueError, TypeError):
            return 0

    try:
        # Sort recipes by calculated popularity in descending order
        ranked_recipes = sorted(recipes, key=calculate_popularity, reverse=True)
    except Exception as e:
        return f"Error: An unexpected error occurred while sorting: {e}"

    return ranked_recipes
@mcp.tool()
def suggest_alternative_queries(original_query, max_attempts=5):
    """
    Suggests alternative or refined search queries to improve the likelihood of finding relevant results.

    Args:
        original_query (str): The user's original search query.
        max_attempts (int): Maximum number of alternative queries to generate. Defaults to 5.

    Returns:
        list: A list of refined search query strings, or an error message if inputs are invalid.
    """
    try:
        # Ensure original_query is a string
        if not isinstance(original_query, str):
            original_query = str(original_query)
        
        # Ensure max_attempts is an integer
        max_attempts = int(max_attempts)
        if max_attempts <= 0:
            return "Error: max_attempts must be a positive integer."

        original_query = original_query.strip()
        if not original_query:
            return "Error: original_query cannot be empty."
    except (ValueError, TypeError):
        return "Error: Invalid input values for original_query or max_attempts."

    variations = []
    base_query = original_query

    # Define common patterns for query variations
    query_patterns = [
        lambda q: f"{q} quick",
        lambda q: f"{q} easy",
        lambda q: f"{q} recipe",
        lambda q: f"healthy {q}",
        lambda q: f"low calorie {q}",
        lambda q: f"best {q}",
        lambda q: f"{q} under 30 minutes",
        lambda q: f"quick {q} recipe",
        lambda q: f"{q} with high ratings",
        lambda q: f"{q} with detailed instructions"
    ]

    # Generate variations within the max_attempts limit
    for pattern in query_patterns:
        if len(variations) >= max_attempts:
            break
        refined_query = pattern(base_query)
        if refined_query not in variations:
            variations.append(refined_query)

    return variations
@mcp.tool()
def filter_and_fetch_recipe_details_by_criteria(query, min_reviews=None, min_rating=None, max_prep_time=None):
    # Validate and convert arguments
    if not isinstance(query, str) or not query.strip():
        return {"error": "Invalid 'query'. It must be a non-empty string."}
    
    try:
        min_reviews = int(min_reviews) if min_reviews is not None else None
        if min_reviews is not None and min_reviews < 0:
            return {"error": "'min_reviews' must be a non-negative integer."}
    except ValueError:
        return {"error": "Invalid 'min_reviews'. It must be an integer."}
    
    try:
        min_rating = float(min_rating) if min_rating is not None else None
        if min_rating is not None and (min_rating < 0 or min_rating > 5):
            return {"error": "'min_rating' must be a float between 0 and 5."}
    except ValueError:
        return {"error": "Invalid 'min_rating'. It must be a float."}
    
    try:
        max_prep_time = int(max_prep_time) if max_prep_time is not None else None
        if max_prep_time is not None and max_prep_time < 0:
            return {"error": "'max_prep_time' must be a non-negative integer."}
    except ValueError:
        return {"error": "Invalid 'max_prep_time'. It must be an integer."}
    
    # Search recipes based on the query
    search_results = search(query=query)
    if not isinstance(search_results, list):
        return {"error": "Unexpected error: 'search' function did not return a list."}
    
    # Filter the search results by the provided criteria
    filtered_recipes = filter_recipes(
        recipes=search_results,
        min_reviews=min_reviews,
        min_rating=min_rating,
        max_prep_time=max_prep_time
    )
    if not isinstance(filtered_recipes, list):
        return {"error": "Unexpected error: 'filter_recipes' function did not return a list."}
    
    # For the first recipe that meets the criteria, fetch detailed information
    if filtered_recipes:
        first_recipe = filtered_recipes[0]
        if 'url' not in first_recipe:
            return {"error": "Unexpected error: Recipe does not contain a 'url' key."}
        
        recipe_url = first_recipe['url']
        recipe_details = get_recipe_details(recipe_url=recipe_url)
        if not recipe_details:
            return {"error": "Failed to fetch recipe details."}
        
        return recipe_details
    
    # Return an empty output if no recipes match the criteria
    return {}
@mcp.tool()
def filter_recipes_by_criteria(recipes, min_rating=0, min_reviews=0, max_prep_time=None):
    """
    Filters a list of recipe summaries based on customizable criteria such as 
    minimum rating, minimum number of reviews, and maximum preparation time.

    Args:
        recipes (list): List of recipes, where each recipe is a dictionary
                        containing 'url', 'rating_value', 'rating_count', and 
                        optionally detailed 'prep_time'.
        min_rating (float): Minimum rating value for a recipe to be included.
        min_reviews (int): Minimum number of reviews for a recipe to be included.
        max_prep_time (int or None): Maximum preparation time (in minutes) for 
                                     a recipe to be included. Set to None to ignore.

    Returns:
        list: Filtered list of recipes that meet all specified conditions.
    """
    def parse_time(time_str):
        """Converts a time string like '1 hr 25 mins' or '15 mins' into total minutes."""
        time_parts = time_str.split()
        total_minutes = 0

        for i in range(0, len(time_parts), 2):
            try:
                unit = time_parts[i + 1]
                value = int(time_parts[i])

                if unit.startswith('hr'):
                    total_minutes += value * 60
                elif unit.startswith('min'):
                    total_minutes += value
            except (IndexError, ValueError):
                # If time string format is invalid, assume 0 minutes
                return 0

        return total_minutes

    # Ensure valid input for min_rating, min_reviews, and max_prep_time
    try:
        min_rating = float(min_rating)
    except (ValueError, TypeError):
        return {"error": "min_rating must be a valid float."}

    try:
        min_reviews = int(min_reviews)
    except (ValueError, TypeError):
        return {"error": "min_reviews must be a valid integer."}

    if max_prep_time is not None:
        try:
            max_prep_time = int(max_prep_time)
        except (ValueError, TypeError):
            return {"error": "max_prep_time must be a valid integer or None."}

    if not isinstance(recipes, list):
        return {"error": "recipes must be a list of dictionaries."}

    filtered_recipes = []
    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue  # Skip entries that are not dictionaries

        try:
            # Validate rating and review count
            rating = float(recipe.get('rating_value', 0))
            reviews = int(recipe.get('rating_count', 0))
            if rating < min_rating or reviews < min_reviews:
                continue

            # Validate preparation time if applicable
            if max_prep_time is not None and 'prep_time' in recipe:
                prep_time_str = recipe.get('prep_time', '0 mins')
                if not isinstance(prep_time_str, str):
                    continue  # Skip if prep_time is not a string
                prep_time_minutes = parse_time(prep_time_str)
                if prep_time_minutes > max_prep_time:
                    continue

            # Add recipe to filtered list if all conditions are met
            filtered_recipes.append(recipe)
        except (ValueError, TypeError):
            # Skip any recipe with unexpected or missing data
            continue

    return filtered_recipes
@mcp.tool()
def filter_recipes(recipes, min_reviews, min_rating):
    """
    Filters a list of recipes based on minimum required review count and average rating.

    Args:
        recipes (list): A list of recipe dictionaries with keys 'title', 'url', 'rating_count', and 'rating_value'.
        min_reviews (int): The minimum number of reviews required for a recipe.
        min_rating (float): The minimum average rating required for a recipe.

    Returns:
        list: A filtered list of recipe dictionaries meeting or exceeding the criteria.
    """
    filtered_recipes = []

    # Ensure types of min_reviews and min_rating are correct
    try:
        min_reviews = int(min_reviews)
        min_rating = float(min_rating)
    except ValueError:
        return {"error": "min_reviews must be an integer and min_rating must be a float."}

    for recipe in recipes:
        try:
            # Parse rating_count and rating_value, with conversion to appropriate types
            rating_count = int(str(recipe.get('rating_count', '0')).replace(',', ''))
            rating_value = float(recipe.get('rating_value', 0))

            # Apply the filters
            if rating_count >= min_reviews and rating_value >= min_rating:
                filtered_recipes.append(recipe)
        except (ValueError, AttributeError):
            # If there is an issue with the data format, skip this recipe
            continue

    return filtered_recipes
@mcp.tool()
def filter_recipe_results(recipes, min_rating=4.5, min_reviews=100, serving_size=None):
    """
    Filters a list of recipe results based on specified criteria such as minimum rating, 
    minimum number of reviews, and optional serving size.

    Args:
        recipes (list): List of recipe dictionaries with keys: 'title', 'url', 'rating_count', 'rating_value'.
        min_rating (float): Minimum rating value to filter recipes.
        min_reviews (int): Minimum number of reviews required for recipes.
        serving_size (int, optional): Optional serving size to match in recipe details. Defaults to None.

    Returns:
        list: Filtered list of recipes meeting the specified conditions, or an empty list in case of an error.
    """
    if not isinstance(recipes, list):
        return {"error": "Invalid type for 'recipes'. Expected a list of dictionaries."}

    try:
        min_rating = float(min_rating)
    except ValueError:
        return {"error": "Invalid type for 'min_rating'. Expected a float."}

    try:
        min_reviews = int(min_reviews)
    except ValueError:
        return {"error": "Invalid type for 'min_reviews'. Expected an integer."}

    if serving_size is not None:
        try:
            serving_size = int(serving_size)
        except ValueError:
            return {"error": "Invalid type for 'serving_size'. Expected an integer or None."}

    filtered_recipes = []
    
    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue  # Skip non-dictionary entries

        try:
            rating_value = float(recipe.get('rating_value', 0))
            rating_count = int(recipe.get('rating_count', 0))
        except (ValueError, TypeError):
            continue  # Skip recipes with invalid rating or review count values

        if rating_value >= min_rating and rating_count >= min_reviews:
            if serving_size is not None:
                if 'url' not in recipe or not isinstance(recipe['url'], str):
                    continue  # Skip if URL is missing or not a string
                details = get_recipe_details(recipe['url'])  # Assumes this is implemented elsewhere
                try:
                    if int(details.get('servings', 0)) == serving_size:
                        filtered_recipes.append(recipe)
                except (ValueError, TypeError):
                    continue
            else:
                filtered_recipes.append(recipe)

    return filtered_recipes
@mcp.tool()
def filter_recipes(recipes, min_rating=0, min_reviews=0, prep_time=None, cook_time=None, max_calories=None, must_have_ingredients=None):
    """
    Filters a given list of recipes based on specified criteria.

    Parameters:
    - recipes (list): A list of recipes returned by the 'search' function.
    - min_rating (float): Minimum rating value required for a recipe.
    - min_reviews (int): Minimum number of reviews required for a recipe.
    - prep_time (int, optional): Maximum preparation time (in minutes) allowed for a recipe.
    - cook_time (int, optional): Maximum cooking time (in minutes) allowed for a recipe.
    - max_calories (int, optional): Maximum calories allowed per serving.
    - must_have_ingredients (list, optional): A list of ingredients that must be present in the recipe.

    Returns:
    - list: A list of recipes that meet the filtering criteria.
    """
    def parse_time(time_str):
        """Converts a time string like '1 hr 15 mins' to total minutes."""
        if not time_str:
            return None
        try:
            time_parts = time_str.split()
            minutes = 0
            for i in range(0, len(time_parts), 2):
                value = int(time_parts[i])
                unit = time_parts[i + 1].lower()
                if "hr" in unit:
                    minutes += value * 60
                elif "min" in unit:
                    minutes += value
            return minutes
        except (ValueError, IndexError):
            return None

    # Ensure arguments are in correct format
    try:
        min_rating = float(min_rating)
        min_reviews = int(min_reviews)
        if prep_time is not None:
            prep_time = int(prep_time)
        if cook_time is not None:
            cook_time = int(cook_time)
        if max_calories is not None:
            max_calories = int(max_calories)
        if must_have_ingredients is not None:
            if not isinstance(must_have_ingredients, list):
                raise ValueError("must_have_ingredients must be a list.")
            must_have_ingredients = [str(ingredient).strip() for ingredient in must_have_ingredients]
    except (ValueError, TypeError):
        return {"error": "Invalid input parameters. Ensure all inputs are correctly formatted."}

    filtered_recipes = []
    for recipe in recipes:
        try:
            if float(recipe.get("rating_value", 0)) < min_rating:
                continue
            if int(recipe.get("rating_count", 0)) < min_reviews:
                continue
            
            if prep_time is not None or cook_time is not None or max_calories is not None or must_have_ingredients:
                details = get_recipe_details(recipe.get("url", ""))
                recipe_prep_time = parse_time(details.get("prep_time"))
                recipe_cook_time = parse_time(details.get("cook_time"))
                recipe_calories = (
                    int(details["nutrition_facts"]["Calories"])
                    if "nutrition_facts" in details and "Calories" in details["nutrition_facts"]
                    else None
                )
                ingredients = (
                    [ingredient["name"] for ingredient in details["ingredients"]]
                    if "ingredients" in details
                    else []
                )

                if prep_time is not None and (recipe_prep_time is None or recipe_prep_time > prep_time):
                    continue
                if cook_time is not None and (recipe_cook_time is None or recipe_cook_time > cook_time):
                    continue
                if max_calories is not None and (recipe_calories is None or recipe_calories > max_calories):
                    continue
                if must_have_ingredients:
                    if not all(ingredient in ingredients for ingredient in must_have_ingredients):
                        continue

            filtered_recipes.append(recipe)
        except Exception as e:
            # If any unexpected error occurs in processing a single recipe, skip it and continue
            continue

    return filtered_recipes
@mcp.tool()
def filter_recipes_by_rating_and_reviews(recipes, min_rating, min_reviews):
    """
    Filters a list of recipes based on a minimum rating and a minimum number of reviews.

    Parameters:
    - recipes: List of dictionaries, each containing keys "rating_value" (float or str) and "rating_count" (int or str).
    - min_rating: Minimum average rating (float).
    - min_reviews: Minimum number of reviews (int).

    Returns:
    - A list of filtered recipes that have a rating_value >= min_rating and rating_count >= min_reviews.
      Returns an empty list if inputs are invalid or if no recipes match.
    """
    # Ensure min_rating and min_reviews are the correct types
    try:
        min_rating = float(min_rating)
        min_reviews = int(min_reviews)
    except (ValueError, TypeError):
        return {"error": "min_rating should be a float and min_reviews should be an integer."}

    if not isinstance(recipes, list):
        return {"error": "recipes should be a list of dictionaries."}

    filtered_recipes = []
    for recipe in recipes:
        try:
            # Ensure recipe is a dictionary and process its values
            if not isinstance(recipe, dict):
                continue

            # Convert rating_value and rating_count to the appropriate types
            rating_value = float(recipe.get('rating_value', 0))
            rating_count = recipe.get('rating_count', 0)
            if isinstance(rating_count, str):
                rating_count = int(rating_count.replace(',', ''))
            else:
                rating_count = int(rating_count)

            # Filter recipes based on conditions
            if rating_value >= min_rating and rating_count >= min_reviews:
                filtered_recipes.append(recipe)
        except (ValueError, KeyError, TypeError):
            continue  # Skip recipes with invalid or missing data

    return filtered_recipes
@mcp.tool()
def filter_recipes_by_criteria(
    recipes, 
    min_reviews=None, 
    min_rating=None, 
    max_prep_time=None, 
    required_ingredients=None
):
    """
    Filters a list of recipe dictionaries based on specified criteria such as minimum reviews,
    minimum rating, maximum preparation time, and required ingredients. 

    Parameters:
    recipes (list): List of dictionaries containing recipe details.
    min_reviews (int, optional): Minimum number of reviews a recipe must have.
    min_rating (float, optional): Minimum rating a recipe must have.
    max_prep_time (int, optional): Maximum preparation time (in minutes).
    required_ingredients (list, optional): List of ingredients that must be present in the recipe.

    Returns:
    list: A list of recipes that match all the given criteria.

    If any of the parameters have incorrect types, an error message will be returned.
    """
    def convert_to_int(value, parameter_name):
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError(f"The parameter '{parameter_name}' must be an integer.")

    def convert_to_float(value, parameter_name):
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"The parameter '{parameter_name}' must be a float.")

    def convert_to_list(value, parameter_name):
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value]
        else:
            raise ValueError(f"The parameter '{parameter_name}' must be a list or a string.")

    def time_to_minutes(time_str):
        """Utility function to convert time format (e.g., '1 hr 15 mins') to minutes."""
        if not time_str or not isinstance(time_str, str):
            return None
        time_parts = time_str.split()
        minutes = 0
        try:
            for i in range(0, len(time_parts), 2):
                value = int(time_parts[i])
                unit = time_parts[i + 1]
                if "hr" in unit:
                    minutes += value * 60
                elif "min" in unit:
                    minutes += value
            return minutes
        except (ValueError, IndexError):
            return None

    try:
        if min_reviews is not None:
            min_reviews = convert_to_int(min_reviews, "min_reviews")
        if min_rating is not None:
            min_rating = convert_to_float(min_rating, "min_rating")
        if max_prep_time is not None:
            max_prep_time = convert_to_int(max_prep_time, "max_prep_time")
        if required_ingredients is not None:
            required_ingredients = convert_to_list(required_ingredients, "required_ingredients")
    
        filtered_recipes = []
        for recipe in recipes:
            if not isinstance(recipe, dict):
                continue
            
            # Check minimum reviews
            if min_reviews is not None and int(recipe.get("rating_count", 0)) < min_reviews:
                continue
            
            # Check minimum rating
            if min_rating is not None and float(recipe.get("rating", 0)) < min_rating:
                continue
            
            # Check maximum preparation time
            if max_prep_time is not None:
                prep_time_str = recipe.get("prep_time", "")
                prep_time_min = time_to_minutes(prep_time_str)
                if prep_time_min is None or prep_time_min > max_prep_time:
                    continue
            
            # Check for required ingredients
            if required_ingredients is not None:
                recipe_ingredients = [ingredient.get("name", "").lower() for ingredient in recipe.get("ingredients", []) if isinstance(ingredient, dict)]
                if not all(req_ing.lower() in recipe_ingredients for req_ing in required_ingredients):
                    continue

            # If all criteria are met
            filtered_recipes.append(recipe)
        
        return filtered_recipes

    except ValueError as e:
        return {"error": str(e)}
@mcp.tool()
def filter_recipes_by_criteria(recipes, min_rating=None, min_reviews=None, max_prep_time=None, required_ingredients=None, approx_servings=None):
    """
    Filters a list of recipes based on user-provided criteria.

    Args:
        recipes (list): List of recipes with details.
        min_rating (float): Minimum average rating required.
        min_reviews (int): Minimum number of reviews required.
        max_prep_time (int): Maximum preparation time in minutes.
        required_ingredients (list): List of ingredients that the recipe must include.
        approx_servings (int): Approximate number of servings required.

    Returns:
        list: A refined list of recipes that match the criteria, or an empty list if none match.
    """
    def parse_time(time_str):
        """Converts time string to minutes."""
        time_units = {"hr": 60, "hrs": 60, "min": 1, "mins": 1}
        try:
            time_parts = time_str.split()
            time_in_minutes = sum(int(time_parts[i]) * time_units[time_parts[i + 1].lower()] for i in range(0, len(time_parts), 2))
            return time_in_minutes
        except Exception:
            return -1  # Return -1 if parsing fails

    def try_convert(value, target_type, default=None):
        """Helper function to safely convert types."""
        try:
            return target_type(value)
        except (ValueError, TypeError):
            return default

    # Ensure required_ingredients is a list
    if required_ingredients is not None:
        if not isinstance(required_ingredients, (list, tuple)):
            try:
                required_ingredients = list(required_ingredients)
            except Exception:
                return {"error": "Invalid format for required_ingredients. Expected a list or tuple."}

    filtered_recipes = []

    for recipe in recipes:
        # Filtering by minimum rating
        if min_rating is not None:
            rating = try_convert(recipe.get("rating", 0), float, 0)
            if rating < min_rating:
                continue
        
        # Filtering by minimum number of reviews
        if min_reviews is not None:
            rating_count = try_convert(recipe.get("rating_count", 0), int, 0)
            if rating_count < min_reviews:
                continue
        
        # Filtering by maximum preparation time
        if max_prep_time is not None:
            prep_time_str = recipe.get("prep_time", "0 mins")
            prep_time = parse_time(prep_time_str)
            if prep_time == -1 or prep_time > max_prep_time:
                continue

        # Filtering by required ingredients
        if required_ingredients is not None:
            ingredients = [item.get("name", "").lower() for item in recipe.get("ingredients", []) if isinstance(item, dict)]
            if not all(ingredient.lower() in ingredients for ingredient in required_ingredients):
                continue

        # Filtering by approximate servings
        if approx_servings is not None:
            servings = try_convert(recipe.get("servings", 0), int, -1)
            if servings != approx_servings:
                continue

        # Add recipe to filtered list if all filters are satisfied
        filtered_recipes.append(recipe)

    return filtered_recipes
@mcp.tool()
def filter_recipes_by_criteria(recipes, min_review_count, min_rating_value):
    """
    Filters a list of recipe objects based on a minimum review count and rating value.
    
    Parameters:
        recipes (list): A list of recipe dictionaries. Each dictionary should contain 'rating_count' and 'rating_value' keys.
        min_review_count (int): The minimum number of reviews a recipe must have to be included in the filtered result.
        min_rating_value (float): The minimum rating value a recipe must have to be included in the filtered result.
    
    Returns:
        list: A list of recipe dictionaries that meet or exceed the specified criteria, or an empty list if inputs are invalid.
    """
    # Ensure inputs are valid
    try:
        min_review_count = int(min_review_count)
        min_rating_value = float(min_rating_value)
    except (ValueError, TypeError):
        return {"error": "min_review_count must be an integer and min_rating_value must be a float"}

    if not isinstance(recipes, list):
        return {"error": "recipes must be a list of dictionaries"}
    
    filtered_recipes = []
    for recipe in recipes:
        try:
            if not isinstance(recipe, dict):
                continue  # Skip if the item is not a dictionary
            rating_count_raw = recipe.get('rating_count', '0')
            rating_count = int(str(rating_count_raw).replace(',', ''))
            rating_value = float(recipe.get('rating_value', 0))
            if rating_count >= min_review_count and rating_value >= min_rating_value:
                filtered_recipes.append(recipe)
        except (ValueError, TypeError, AttributeError):
            continue  # Skip this recipe if there is an issue with parsing values
    return filtered_recipes
@mcp.tool()
if __name__ == "__main__":
    mcp.run(transport='stdio')
