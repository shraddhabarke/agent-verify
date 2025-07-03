def check_ingredient_presence(recipe_details, ingredient):
    """
    Check if a specific ingredient is present in a recipe's list of ingredients.

    :param recipe_details: Dictionary containing detailed information about a recipe.
                           The dictionary must have an 'ingredients' key, which is a list of ingredient strings.
    :param ingredient:     String representing the ingredient to check for.
    :return:               Boolean value - True if the ingredient is present, False otherwise.
    """
    # Handle potential issues if recipe_details is not a dictionary
    if not isinstance(recipe_details, dict):
        raise ValueError("recipe_details must be a dictionary")

    # Handle potential issues if ingredient is not a string
    if not isinstance(ingredient, str):
        raise ValueError("ingredient must be a string")

    # Get the list of ingredients from recipe_details, defaulting to an empty list if the key doesn't exist or is not a list
    ingredients = recipe_details.get('ingredients', [])
    if not isinstance(ingredients, list):
        raise ValueError("ingredients must be a list of strings in the recipe_details dictionary")

    # Ensure all items in the ingredients list are strings
    if not all(isinstance(item, str) for item in ingredients):
        raise ValueError("All ingredients in the list must be strings")

    # Perform the check
    return any(ingredient.lower() in ingredient_item.lower() for ingredient_item in ingredients)


# Unit tests
def test_check_ingredient_presence():
    # Test case 1: Ingredient is in the recipe
    recipe_details = {
        'title': 'Vegetarian Lasagna',
        'ingredients': ['1 cup ricotta cheese', '2 cups mozzarella cheese', '1 zucchini sliced', '1 cup pasta sauce']
    }
    assert check_ingredient_presence(recipe_details, 'zucchini') == True

    # Test case 2: Ingredient is not in the recipe
    recipe_details = {
        'title': 'Vegan Chocolate Chip Cookies',
        'ingredients': ['2 cups flour', '1 tsp baking soda', '1/2 cup vegan chocolate chips']
    }
    assert check_ingredient_presence(recipe_details, 'zucchini') == False

    # Test case 3: Ingredient is a substring of another ingredient
    recipe_details = {
        'title': 'Spinach Artichoke Lasagna',
        'ingredients': ['1 cup spinach leaves', '2 cups ricotta cheese', '1/2 cup artichoke hearts']
    }
    assert check_ingredient_presence(recipe_details, 'spin') == True

    # Test case 4: Recipe has no ingredients list
    recipe_details = {'title': 'Mystery Recipe'}
    assert check_ingredient_presence(recipe_details, 'zucchini') == False

    # Test case 5: Case insensitivity in ingredient matching
    recipe_details = {
        'title': 'Cheese Lasagna',
        'ingredients': ['1 cup Ricotta Cheese', '2 cups Mozzarella Cheese', '1 Zucchini']
    }
    assert check_ingredient_presence(recipe_details, 'ZUCCHINI') == True

    # Test case 6: recipe_details is not a dictionary
    try:
        check_ingredient_presence(['1 cup sugar', '2 cups flour'], 'sugar')
    except ValueError as e:
        assert str(e) == "recipe_details must be a dictionary"

    # Test case 7: ingredient is not a string
    recipe_details = {
        'title': 'Simple Recipe',
        'ingredients': ['1 cup flour', '1/2 cup sugar']
    }
    try:
        check_ingredient_presence(recipe_details, 123)
    except ValueError as e:
        assert str(e) == "ingredient must be a string"

    # Test case 8: ingredients list contains non-string items
    recipe_details = {
        'title': 'Weird Recipe',
        'ingredients': ['1 cup water', 42, '1/2 cup sugar']
    }
    try:
        check_ingredient_presence(recipe_details, 'sugar')
    except ValueError as e:
        assert str(e) == "All ingredients in the list must be strings"

    # Test case 9: ingredients is not a list
    recipe_details = {
        'title': 'Invalid Recipe',
        'ingredients': '1 cup water, 1/2 cup sugar'
    }
    try:
        check_ingredient_presence(recipe_details, 'sugar')
    except ValueError as e:
        assert str(e) == "ingredients must be a list of strings in the recipe_details dictionary"

    print("All tests passed.")

# Run the unit tests
test_check_ingredient_presence()