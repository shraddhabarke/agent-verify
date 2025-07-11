@mcp.tool()
def get_recipe_ingredients_and_times(recipe_url):
    '''
    Given a recipe URL (string), retrieves detailed information for the recipe using get_recipe_details, 
    and returns a JSON string containing the recipe title, a list of key ingredients (with quantity, unit, and name),
    and total preparation and cook time (if available).
    '''
    import json
    # Try to convert URL to string (handles if called with non-string types)
    try:
        url_str = str(recipe_url)
        if not url_str.strip():
            raise ValueError("Empty URL provided.")
    except Exception as e:
        return json.dumps({"error": "Invalid recipe_url argument", "exception": str(e)})
    # Fetch detailed recipe info (as a string)
    try:
        details_json_str = get_recipe_details(url_str)
    except Exception as e:
        return json.dumps({"error": "Error in fetching recipe details", "exception": str(e)})
    # Parse the JSON response (usually single-item response list)
    try:
        details_list = json.loads(details_json_str)
        if isinstance(details_list, list) and len(details_list) > 0 and isinstance(details_list[0], dict) and 'text' in details_list[0]:
            try:
                details = json.loads(details_list[0]['text']) if isinstance(details_list[0]['text'], str) else details_list[0]['text']
            except Exception as e:
                return json.dumps({"error": "Failed to parse details_list[0]['text'] as JSON", "exception": str(e)})
        elif isinstance(details_list, dict):
            details = details_list
        else:
            return json.dumps({"error": "Recipe details not found or in unexpected format"})
    except Exception as e:
        return json.dumps({"error": "Could not parse recipe details", "exception": str(e)})
    result = {}
    # Get title
    result['title'] = details.get('title', '')
    # Get ingredients (if available and is a list)
    ingredients = details.get('ingredients', [])
    # Try to coerce ingredients to a list of dicts if it's in an unexpected format
    if isinstance(ingredients, str):
        try:
            ingredients = json.loads(ingredients)
        except Exception:
            ingredients = [ingredients]
    # Ensure it's a list
    if not isinstance(ingredients, list):
        ingredients = [ingredients]
    result['ingredients'] = ingredients
    # Get times, ensure strings
    prep = details.get('prep_time', '')
    cook = details.get('cook_time', '')
    total = details.get('total_time', '')
    result['prep_time'] = str(prep) if prep is not None else ''
    result['cook_time'] = str(cook) if cook is not None else ''
    result['total_time'] = str(total) if total is not None else ''
    try:
        return json.dumps(result)
    except Exception as e:
        # Fallback: just return error
        return json.dumps({"error": "Could not serialize result to JSON", "exception": str(e), "result": str(result)})
    

def filter_recipes(recipes_json_str, min_rating=None, min_reviews=None, max_calories=None, max_prep_time=None, required_ingredients=None, min_servings=None):
    import json
    import re
    # NEW: Accept input as Python list/dict or string. If list/dict, convert to JSON string.
    if isinstance(recipes_json_str, (list, dict)):
        try:
            recipes_json_str = json.dumps(recipes_json_str)
        except Exception as e:
            return json.dumps({'error': 'Could not convert input list/dict to JSON string: %s' % str(e)})
    try:
        if not isinstance(recipes_json_str, str):
            recipes_json_str = str(recipes_json_str)
        # Remove any leading/trailing whitespace before parsing
        recipes = json.loads(recipes_json_str.strip())
        if not isinstance(recipes, list):
            raise ValueError("recipes_json_str does not contain a list")
    except Exception as e:
        return json.dumps({"error": f"Failed to parse recipes_json_str: {str(e)}"})
    def parse_number(val):
        try:
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return val
            val = str(val).replace(",", "").strip()
            if val == '':
                return None
            if "." in val:
                return float(val)
            return int(val)
        except Exception as e:
            return None
    def parse_time_to_minutes(time_str):
        if time_str is None:
            return None
        try:
            if isinstance(time_str, (int, float)):
                return int(time_str)
            time_str = str(time_str).lower().strip()
            if time_str == "":
                return None
            # Try HH:MM:SS
            m = re.match(r"^(\d+):(\d+):(\d+)$", time_str)
            if m:
                h, mi, s = map(int, m.groups())
                return h*60+mi+(s//60)
            minutes = 0
            h_match = re.search(r"(\d+)\s*hr", time_str)
            if h_match:
                minutes += int(h_match.group(1))*60
            m_match = re.search(r"(\d+)\s*min", time_str)
            if m_match:
                minutes += int(m_match.group(1))
            if minutes==0:
                n = parse_number(time_str)
                if n is not None:
                    minutes = int(n)
            return minutes if minutes>0 else None
        except Exception as e:
            return None
    def ingredient_in_recipe(recipe, req_ingredient):
        if not req_ingredient:
            return True
        req_ingredient = req_ingredient.lower()
        if "ingredients" in recipe:
            for ing in recipe["ingredients"]:
                try:
                    if isinstance(ing, dict) and "name" in ing:
                        line = ing["name"].lower()
                    else:
                        line = str(ing).lower()
                    if req_ingredient in line:
                        return True
                except Exception:
                    continue
            return False
        return True
    def get_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except Exception:
            try:
                return float(parse_number(val))
            except Exception:
                return None
    def get_int(val):
        if val is None:
            return None
        try:
            return int(val)
        except Exception:
            try:
                return int(float(val))
            except Exception:
                return None
    def get_str(val):
        if val is None:
            return None
        return str(val)
    min_rating = get_float(min_rating)
    min_reviews = get_int(min_reviews)
    max_calories = get_float(max_calories)
    max_prep_time = get_str(max_prep_time)
    required_ingredients = get_str(required_ingredients)
    min_servings = get_int(min_servings)
    req_ings = []
    if required_ingredients:
        req_ings = [ri.strip() for ri in required_ingredients.split(',') if ri.strip()]
    results = []
    for recipe in recipes:
        try:
            if min_rating is not None:
                rating_val = parse_number(recipe.get("rating_value", recipe.get("rating", 0)))
                if rating_val is None or rating_val < min_rating:
                    continue
            if min_reviews is not None:
                rc = parse_number(recipe.get("rating_count", recipe.get("review_count", 0)))
                if rc is None or rc < min_reviews:
                    continue
            if max_calories is not None:
                cals = None
                if 'nutrition_facts' in recipe and isinstance(recipe["nutrition_facts"], dict):
                    cals = parse_number(recipe["nutrition_facts"].get("Calories", None))
                elif "calories" in recipe:
                    cals = parse_number(recipe["calories"])
                if cals is not None and cals > max_calories:
                    continue
            if max_prep_time is not None:
                rprep = recipe.get("prep_time") or recipe.get("total_time") or recipe.get("cook_time")
                rpmins = parse_time_to_minutes(rprep)
                mpmins = parse_time_to_minutes(max_prep_time)
                if rpmins is not None and mpmins is not None and rpmins > mpmins:
                    continue
            passed = True
            for ri in req_ings:
                if not ingredient_in_recipe(recipe, ri):
                    passed = False
                    break
            if not passed:
                continue
            if min_servings is not None:
                servings = parse_number(recipe.get("servings", None))
                if servings is not None and servings < min_servings:
                    continue
            results.append(recipe)
        except Exception as e:
            continue
    try:
        return json.dumps(results)
    except Exception as e:
        return json.dumps({"error": f"Failed to serialize results: {str(e)}"})
    

@mcp.tool()
def filter_recipes(recipe_list_str, min_rating_str=None, min_reviews_str=None, max_calories_str=None, must_have_ingredients_str=None, exclude_ingredients_str=None, max_prep_minutes_str=None, min_servings_str=None):
    """
    Filters a list of recipes by various criteria such as minimum rating, minimum number of reviews, maximum calories per serving, required or excluded ingredients, maximum preparation time (in minutes), and minimum servings.
    Parameters:
        recipe_list_str (str): JSON list of recipes (each as returned by search; requires at least 'url', 'rating_value', and 'rating_count').
        min_rating_str (str, optional): Minimum rating value required (e.g., '4.5').
        min_reviews_str (str, optional): Minimum number of reviews required (e.g., '60').
        max_calories_str (str, optional): Maximum calories per serving allowed (e.g., '600').
        must_have_ingredients_str (str, optional): Required ingredients, comma-separated (e.g., 'zucchini,spinach').
        exclude_ingredients_str (str, optional): Ingredients to exclude, comma-separated (e.g., 'eggplant').
        max_prep_minutes_str (str, optional): Maximum preparation time in minutes (e.g., '30').
        min_servings_str (str, optional): Minimum servings required (e.g., '6').
    Returns:
        str: JSON string of recipes that match all the specified criteria, with full details included (uses get_recipe_details for filtering).
    """
    import json
    import logging
    # Parse recipe list
    try:
        if isinstance(recipe_list_str, str):
            recipe_list = json.loads(recipe_list_str)
        elif isinstance(recipe_list_str, list):
            recipe_list = recipe_list_str
        else:
            raise ValueError(f"recipe_list_str should be a JSON string or a list, got: {type(recipe_list_str)}")
    except Exception as e:
        return json.dumps({'error': f'Could not parse recipes input: {e}'})
    # Prepare filters with robust conversion
    def _to_float(x):
        try:
            if x is None:
                return None
            if isinstance(x, (float, int)):
                return float(x)
            if isinstance(x, str):
                x = x.strip()
                return float(x)
            return float(x)
        except Exception as e:
            return None

    def _to_int(x):
        try:
            if x is None:
                return None
            if isinstance(x, int):
                return x
            if isinstance(x, float):
                return int(x)
            if isinstance(x, str):
                x = x.replace(',', '').strip()
                return int(float(x) if '.' in x else x)
            return int(x)
        except Exception:
            return None
    
    min_rating = _to_float(min_rating_str)
    min_reviews = _to_int(min_reviews_str)
    max_calories = _to_float(max_calories_str)
    max_prep_minutes = _to_int(max_prep_minutes_str)
    min_servings = _to_int(min_servings_str)
    def _to_ingredient_list(s):
        if not s:
            return []
        if isinstance(s, list):
            # LLM might pass a list
            return [str(x).strip().lower() for x in s]
        try:
            # Sometimes the LLM might pass a stringified list
            if s.strip().startswith("[") and s.strip().endswith("]"):
                from ast import literal_eval
                parsed = literal_eval(s)
                if isinstance(parsed, list):
                    return [str(x).strip().lower() for x in parsed]
        except Exception:
            pass
        # Otherwise, assume comma-separated string
        return [x.strip().lower() for x in str(s).split(',') if x.strip()]

    must_have_ingredients = _to_ingredient_list(must_have_ingredients_str)
    exclude_ingredients = _to_ingredient_list(exclude_ingredients_str)

    # Helper for extracting time in minutes
    def extract_minutes(time_str):
        import re
        if not time_str:
            return 0
        mins = 0
        hour_match = re.search(r"(\d+)\s*hr", time_str)
        min_match = re.search(r"(\d+)\s*min", time_str)
        if hour_match:
            mins += int(hour_match.group(1)) * 60
        if min_match:
            mins += int(min_match.group(1))
        return mins

    filtered = []
    for recipe in recipe_list:
        try:
            # Apply search-level filters
            rating_value = _to_float(recipe.get('rating_value', 0))
            rating_count = _to_int(recipe.get('rating_count', 0))
            if min_rating is not None and (rating_value is None or rating_value < min_rating):
                continue
            if min_reviews is not None and (rating_count is None or rating_count < min_reviews):
                continue
            # Must have URL
            if 'url' not in recipe:
                continue
            # Get full details
            try:
                details_raw = get_recipe_details(recipe['url'])
                details = json.loads(details_raw) if isinstance(details_raw, str) else details_raw
            except Exception as e:
                # Cannot fetch or parse details
                continue
            # Calories
            if max_calories is not None:
                cal_str = details.get('nutrition_facts', {}).get('Calories', '')
                cal_str = str(cal_str).strip()
                cal = None
                if cal_str:
                    try:
                        cal = float(''.join(c for c in cal_str if (c.isdigit() or c == '.')))
                    except:
                        cal = None
                if cal is not None and cal > max_calories:
                    continue
            # Prep time
            if max_prep_minutes is not None:
                prep_time_str = str(details.get('prep_time', ''))
                prep_time_min = extract_minutes(prep_time_str)
                if prep_time_min > max_prep_minutes:
                    continue
            # Servings
            if min_servings is not None:
                servings_str = str(details.get('servings', ''))
                servings = None
                try:
                    servings = _to_int(''.join(filter(lambda c: c.isdigit() or c=='.', servings_str)))
                except:
                    servings = None
                if servings is not None and servings < min_servings:
                    continue
            # Ingredients
            ingredient_objs = details.get('ingredients', [])
            # Each ingredient in ingredient_objs should have a string property 'name'
            recipe_ingredients = []
            try:
                recipe_ingredients = [i['name'].lower() for i in ingredient_objs if isinstance(i, dict) and 'name' in i and isinstance(i['name'], str)]
            except Exception as e:
                recipe_ingredients = []
            if must_have_ingredients:
                if not all(any(req in ing for ing in recipe_ingredients) for req in must_have_ingredients):
                    continue
            if exclude_ingredients:
                if any(ex in ing for ex in exclude_ingredients for ing in recipe_ingredients):
                    continue
            # Passes all
            filtered.append(details)
        except Exception as e:
            # Unexpected error: log or collect
            logging.error(f"filter_recipes error for recipe: {e} -- input: {repr(recipe)}")
    try:
        return json.dumps(filtered)
    except Exception as e:
        return json.dumps({'error': f'Could not serialize filtered recipes: {e}'})
    


def extract_ingredients_and_steps(recipe_details_str):
    """
    Given a detailed recipe dictionary (as string or dict), this function extracts and returns a standardized list of key ingredients (with quantities, units, and names) and a list of preparation or cooking steps/directions.
    Args:
        recipe_details_str: JSON string or dict of the recipe details as provided by get_recipe_details.
    Returns:
        str: JSON object with 'ingredients' (list of dicts with 'quantity', 'unit', 'name') and 'directions' (list of strings for steps).
    """
    import json
    # Handle the case where input may already be a dict
    try:
        if isinstance(recipe_details_str, dict):
            recipe = recipe_details_str
        else:
            # Try to convert to string before loading as JSON, as LLM might pass non-string
            recipe_str = recipe_details_str
            if not isinstance(recipe_str, str):
                try:
                    recipe_str = str(recipe_details_str)
                except Exception as e:
                    return json.dumps({
                        "error": f"Input could not be converted to string: {e}",
                        "input": str(recipe_details_str)
                    })
            try:
                recipe = json.loads(recipe_str)
            except Exception as e:
                return json.dumps({
                    "error": f"Input string could not be parsed as JSON: {e}",
                    "input": recipe_str
                })
        # Extract the 'ingredients' and 'directions' in a robust way
        ingredients = recipe.get('ingredients')
        if not isinstance(ingredients, list):
            ingredients = []
        directions = recipe.get('directions')
        if not isinstance(directions, list):
            directions = []
        result = {
            'ingredients': ingredients,
            'directions': directions
        }
        return json.dumps(result)
    except Exception as e:
        import traceback
        return json.dumps({
            "error": f"Unhandled exception: {e}",
            "trace": traceback.format_exc(),
            "input": str(recipe_details_str)
        })
    
@mcp.tool()
def extract_nutrition_label(recipe_details_str):
    """
    Given a detailed recipe dictionary (in string or dict format as returned by get_recipe_details),
    this function extracts and returns the full nutrition label as a standardized dictionary, including
    all available micronutrients (e.g., Iron, Calcium, Vitamin C), macronutrients, calories, and serving information.
    This enables quick access to specific nutritional values such as Iron per serving.
    Args:
        recipe_details_str (str or dict): Recipe details as a JSON string or dict as provided by get_recipe_details.
    Returns:
        str: JSON string of the full nutrition label dictionary with all available nutrient data and serving info.
    """
    import json
    # Defensive: Try to parse string to dict if possible
    details = None
    if isinstance(recipe_details_str, str):
        try:
            details = json.loads(recipe_details_str)
        except json.JSONDecodeError:
            # Sometimes LLM may pass a string representation of a dictionary (not proper JSON)
            try:
                # Try eval as a last resort, but risky and should be avoided in production
                details = eval(recipe_details_str, {"__builtins__": {}})
                if not isinstance(details, dict):
                    raise ValueError("Parsed object is not a dictionary.")
            except Exception as e:
                return json.dumps({
                    "error": f"Could not parse recipe details from string: {str(e)}",
                    "input_type": str(type(recipe_details_str)),
                    "input_preview": recipe_details_str[:200] if isinstance(recipe_details_str, str) else str(recipe_details_str)[:200]
                })
    elif isinstance(recipe_details_str, dict):
        details = recipe_details_str
    else:
        return json.dumps({
            "error": "Input must be either a JSON string or a dictionary.",
            "input_type": str(type(recipe_details_str)),
            "input_preview": str(recipe_details_str)[:200]
        })

    # Now, details should be a dict
    nutrition_label = {}
    if not isinstance(details, dict):
        return json.dumps({
            "error": "Parsed or provided object is not a dictionary.",
            "input_type": str(type(details)),
            "input_preview": str(details)[:200]
        })
    # Extract nutrition facts
    if 'nutrition_facts' in details:
        n_facts = details['nutrition_facts']
        if isinstance(n_facts, str):
            try:
                n_facts = json.loads(n_facts)
            except Exception:
                try:
                    n_facts = eval(n_facts, {"__builtins__": {}})
                except Exception:
                    n_facts = {}
        if isinstance(n_facts, dict):
            nutrition_label.update(n_facts)
    # Add serving/yield info if available
    if 'servings' in details:
        nutrition_label['servings'] = details['servings']
    if 'yield' in details:
        nutrition_label['yield'] = details['yield']
    if not nutrition_label:
        return json.dumps({
            "error": "nutrition_facts not found in input or could not be parsed.",
            "input_keys": list(details.keys())
        })
    return json.dumps(nutrition_label)


@mcp.tool()
def extract_reviews(recipe_details_str):
    '''
    Given a detailed recipe dictionary (string or dict as returned by get_recipe_details),
    this function extracts and returns a list of all user reviews for the recipe.
    Each review in the list contains:
        - review_text (str): The text of the user review.
        - reviewer_name (str, optional): Name of the reviewer, if available.
        - date (str, optional): Date of the review, if available.
        - rating (str or float, optional): Rating provided by the user for that review, if available.
    Returns:
        str: A JSON string of the reviews list, sorted by newest first if possible.
    '''
    import json
    
    # Safely process input argument to ensure we have a recipe dict
    try:
        if isinstance(recipe_details_str, str):
            try:
                recipe = json.loads(recipe_details_str)
            except Exception as e:
                return json.dumps({"error": f"Couldn't load recipe details from string. Error: {str(e)}"})
        elif isinstance(recipe_details_str, dict):
            recipe = recipe_details_str
        else:
            try:
                # Attempt to convert to dict (if e.g., passed as a list of pairs)
                recipe = dict(recipe_details_str)
            except Exception as e:
                return json.dumps({"error": f"Input recipe_details_str is not a valid string or dict. Error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Problem handling recipe_details_str. Error: {str(e)}"})

    # --- ADDED: ensure all keys are lower-cased for flexible matching ---
    if isinstance(recipe, dict):
        recipe = {k.lower(): v for k, v in recipe.items()}
    # --- END ADDED ---

    # Look for all typical keys that could contain reviews.
    reviews = None
    for key in ['reviews', 'user_reviews', 'comments', 'ratings', 'feedback']:
        # --- ADDED: check lowercased keys for flexibility ---
        if key in recipe:
            reviews = recipe[key]
            break
    
    if reviews is None:
        # Return empty array if nothing found
        return json.dumps([])
    
    # Sometimes reviews may not be a list (e.g., single dict)
    if isinstance(reviews, dict):
        reviews = [reviews]
    elif not isinstance(reviews, list):
        # Try to coerce into a list if possible
        try:
            reviews = list(reviews)
        except Exception as e:
            return json.dumps({"error": f"Expected reviews to be a list or dict. Error: {str(e)}"})

    out = []
    for review in reviews:
        # Each review should be a dict. If not, skip or handle error gracefully
        if not isinstance(review, dict):
            try:
                # Try to load as dict from JSON string
                if isinstance(review, str):
                    review = json.loads(review)
                else:
                    continue
            except Exception:
                continue
        # --- ADDED: Lowercase keys for each review dict for flexible access ---
        if isinstance(review, dict):
            review = {k.lower(): v for k, v in review.items()}
        # --- END ADDED ---
        # Try to get relevant fields; be robust to missing fields
        review_text = review.get('text') or review.get('review') or review.get('body') or ''
        reviewer_name = review.get('user') or review.get('reviewer') or review.get('author') or None
        date = review.get('date') or review.get('created_at') or review.get('timestamp') or None
        rating = review.get('rating') or review.get('stars') or None
        out.append({
            'review_text': str(review_text) if review_text is not None else '',
            'reviewer_name': str(reviewer_name) if reviewer_name is not None else None,
            'date': str(date) if date is not None else None,
            'rating': rating
        })
    # Sort by newest if date is available
    try:
        out.sort(key=lambda r: r['date'] or '', reverse=True)
    except Exception:
        pass
    return json.dumps(out)

@mcp.tool()
def extract_total_time_and_servings(recipe_details_str):
    """
    Given a detailed recipe dictionary (as string or dict, as returned by get_recipe_details),
    extracts and returns the 'total_time' and 'servings' fields as a JSON string.
    Args:
        recipe_details_str: JSON string or dict containing recipe details.
    Returns:
        str: JSON string containing 'total_time' and 'servings' keys or error message.
    """
    import json
    import ast
    
    recipe = None
    # Try to parse input if it's a string
    if isinstance(recipe_details_str, str):
        try:
            recipe = json.loads(recipe_details_str)
        except Exception:
            try:
                # Try to use ast.literal_eval to be safer than eval
                recipe = ast.literal_eval(recipe_details_str)
            except Exception as e:
                return json.dumps({'error': f'Input string could not be parsed as JSON or dict: {str(e)}'})
    elif isinstance(recipe_details_str, dict):
        recipe = recipe_details_str
    else:
        return json.dumps({'error': f'Input must be a dict or a string but got {type(recipe_details_str).__name__}'})

    # Validate recipe is a dict
    if not isinstance(recipe, dict):
        return json.dumps({'error': f'Parsed recipe is not a dict but {type(recipe).__name__}.'})
    
    total_time = recipe.get('total_time', None)
    servings = recipe.get('servings', None)
    return json.dumps({'total_time': total_time, 'servings': servings})
@mcp.tool()
def extract_recipe_summary(recipe_details_str):
    """
    Given a detailed recipe dictionary (as a string or dict from get_recipe_details),
    extracts and returns a concise summary including:
        - recipe title
        - description
        - standardized list of key ingredients (with quantities, units, names)
        - prep time, cook time, and total time
        - a brief overview (up to 5 steps) of the main cooking instructions.
    This is ideal for quickly presenting the most important information to users in recipe search tasks.

    Args:
        recipe_details_str (str or dict): Recipe details as returned by get_recipe_details (string or dict)
    Returns:
        str: JSON string containing the summarized recipe information.
    """
    import json
    # 1. Robustly parse input to dict
    recipe = None
    if isinstance(recipe_details_str, dict):
        recipe = recipe_details_str
    elif isinstance(recipe_details_str, str):
        try:
            # Try loading as JSON string
            recipe = json.loads(recipe_details_str)
        except Exception as e:
            # If not valid JSON, try to eval as dict string
            try:
                import ast
                recipe = ast.literal_eval(recipe_details_str)
                if not isinstance(recipe, dict):
                    return json.dumps({'error': 'Input string is neither valid JSON nor a dict representation.'})
            except Exception:
                return json.dumps({'error': f'Could not parse recipe_details_str: {str(e)}'})
    else:
        return json.dumps({'error': f'Input type {type(recipe_details_str)} not supported. Expecting str or dict.'})

    # 2. Extract key information
    title = recipe.get('title', '')
    description = recipe.get('description', '')
    prep_time = recipe.get('prep_time', '')
    cook_time = recipe.get('cook_time', '')
    total_time = recipe.get('total_time', '')

    # 3. Try to use extract_ingredients_and_steps if available, fallback to recipe
    try:
        # Defensive: extract_ingredients_and_steps may expect a string
        if 'extract_ingredients_and_steps' in globals():
            try:
                ias_result = extract_ingredients_and_steps(json.dumps(recipe))
            except Exception:
                ias_result = extract_ingredients_and_steps(recipe)
            try:
                ias = json.loads(ias_result) if isinstance(ias_result, str) else ias_result
            except Exception:
                ias = {}
            ingredients = ias.get('ingredients', recipe.get('ingredients', []))
            directions = ias.get('directions', recipe.get('directions', []))
        else:
            ingredients = recipe.get('ingredients', [])
            directions = recipe.get('directions', [])
    except Exception as e:
        # Fallback for catastrophic errors
        ingredients = recipe.get('ingredients', [])
        directions = recipe.get('directions', [])
    # 4. Only include up to 5 steps in main_steps
    if isinstance(directions, list):
        summary_steps = directions[:5]
    elif isinstance(directions, str):
        summary_steps = [directions]
    else:
        summary_steps = []
    # 5. Compose summary dict
    summary = {
        'title': title,
        'description': description,
        'prep_time': prep_time,
        'cook_time': cook_time,
        'total_time': total_time,
        'ingredients': ingredients,
        'main_steps': summary_steps
    }
    try:
        return json.dumps(summary)
    except Exception as e:
        return json.dumps({'error': f'Failed to serialize summary: {str(e)}', 'summary': str(summary)})