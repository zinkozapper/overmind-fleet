import os
from typing import Literal
import re

try:
    from kubernetes import client, config, utils
except ImportError as e:
    print("Error importing kubernetes, please install it with pip: pip3 install kubernetes")
    userInput =input("If you choose to continue you will not be able to create PVCs. Would you like to continue? (y/n): ")
    if userInput.lower() != "y":
        exit(1)


def makedir(path: str):
    try:
        # Prevent errors from occurring when the directory has already been created.
        if not os.path.exists(path):
            os.mkdir(path)
    except OSError:
        print("Creation of the directory %s failed" % path)

def list_files(directory: str) -> list[str]:
    returlist = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.is_file():
                returlist.append(entry.name)
    return returlist
                


def get_stack_name() -> str:
    """Shared function to get the name of the stack from the user

    Returns:
        str: Name of the stack to create
    """
    return get_string_from_input("Enter the name of the stack (ex. lytle) *NEVER append '-beta' here: ")


def get_valid_ingress_type() -> Literal["frontend", "api"]:
    """Gets the ingress type from the user, either frontend or api

    Returns:
        Literal["frontend", "api"]: ingress type
    """
    result = get_string_from_input(
        "Enter the host for the ingress (ex. lytle.byu.edu): "
    )
    if result == "frontend" or result == "api":
        return result
    else:
        print("Please enter a valid ingress type")
        return get_valid_ingress_type()


def get_namespace(default: str) -> str:
    """Gets the namespace to deploy to, if the user does not provide one, it will default to the default provided

    Args:
        default (str): Default namespace to deploy to

    Returns:
        str: Namespace to deploy to
    """
    return get_string_from_input(
        "Enter the namespace to deploy to (defaults to web): ", default
    )


def get_string_from_input(prompt: str, default_value: str | int = "") -> str:
    """Get string from user input safely, providing an escape hatch if there is a sane default value

    Args:
        prompt (str): Prompt for the user
        default_value (str, optional): default value to fall back on, if provided and user does not provide anything. Defaults to "".

    Returns:
        str: String from user input, or default value if provided and user does not provide anything
    """
    result = input(prompt)
    if result == "" and default_value != "":
        return default_value
    elif result == "":
        print("Please enter a valid string")
        return get_string_from_input(prompt)
    return result


def build_stack():
    """Builds an entire stack, including frontend, backend, database and ingress"""
    print("Creating a new Stack")
    print("This will create a new frontend, backend, and ingress")
    # Frontend and backend now handle creating their own ingress
    build_frontend()
    backend()
    #create_database(name)


def build_frontend(
    subfolder: str | None = None,
    name: str | None = None,
    namespace: str | None = None,
):
    """
    Creates a new frontend from template and writes to a new file
    Args:
        name (str | None, optional): Name of the stack. Defaults to None.
    """
    print("Creating a new Frontend")

    image = get_string_from_input(
        "Enter the frontend image (ex. ghcr.io/byu-life-sciences/lytle-react): "
    )

    name = image.split("/")[-1].split(" ")[0].split("#")[0].split(":")[0].split("@")[0]
    subfolder = input('''      
NOTE: Only put files in BETA subfolder if the image is compiled from the BETA BRANCH of a repository. 
      If a beta websites are in a repo that is still in the MAIN BRANCH, put the files in the MAIN subfolder.
Create in main or beta subfolder (main/beta)? ''')
    if subfolder == "beta":
        name = name + "-beta"
    namespace = get_namespace("web")

    port = get_string_from_input(
        "Enter the port for the frontend (defaults to 3000): ", "3000"
    )

    makedir(f"{subfolder}/{name.split('-api')[0].split('-beta')[0]}")

    # Read in the frontend template
    template = open("templates/frontend-template.yml", "r")
    template = template.read()
    template = template.replace("<NAME>", name)
    template = template.replace("<IMAGE>", image)
    template = template.replace("<PORT>", port)
    template = template.replace("<NAMESPACE>", namespace)

    # Write the template to a new file
    new_file = open(f"{subfolder}/{name.split('-api')[0].split('-beta')[0]}/{name}.yml", "w")
    new_file.write(template)
    new_file.close()

    should_create_ingress = get_string_from_input(
        "Would you like to create an ingress for this frontend? (y/n): ", "n"
    )

    if should_create_ingress.lower() == "y":
        ingress(subfolder, name, "frontend", port, namespace)
    else:
        print("Skipping ingress creation")


def backend(subfolder: str | None = None, name: str | None = None, namespace: str | None = None):
    """Builds a backend from template

    Args:
        name (str | None, optional): Name of the stack. Defaults to None.
        namespace (str | None, optional): namespace to create the stack in. Defaults to Web. Defaults to None.
    """
    print("Creating a new Backend")

    image = get_string_from_input(
        "Enter the backend image (ex. ghcr.io/byu-life-sciences/lytle-api): "
    )

    name = image.split("/")[-1].split(" ")[0].split("#")[0].split(":")[0].split("@")[0]
    subfolder = input('''      
NOTE: Only put files in BETA subfolder if the image is compiled from the BETA BRANCH of a repository. 
      If a beta websites are in a repo that is still in the MAIN BRANCH, put the files in the MAIN subfolder.
Create in main or beta subfolder (main/beta)? ''')
    if subfolder == "beta":
        name = name + "-beta"
    namespace = get_namespace("web")

    makedir(f"{subfolder}/{name.split('-api')[0].split('-beta')[0]}")
    
    # Read in the backend template
    template = open("templates/api-template.yml", "r")
    template = template.read()
    template = template.replace("<NAME>", name)
    template = template.replace("<IMAGE>", image)
    template = template.replace("<NAMESPACE>", namespace)

    # Write the template to a new file
    new_file = open(f"{subfolder}/{name.split('-api')[0].split('-beta')[0]}/{name}.yml", "w")
    new_file.write(template)
    new_file.close()

    should_create_ingress = get_string_from_input(
        "Would you like to create an ingress for this backend? (y/n): ", "n"
    )

    if should_create_ingress.lower() == "y":
        # Default this ingress to port 80
        ingress(subfolder, name, "api", "8080", namespace)
    else:
        print("Skipping ingress creation")



def ingress(
    subfolder: str | None = None,
    stack_name: str | None = None,
    ingress_type: Literal["frontend", "api"] | None = None,
    port: str | None = None,
    namespace: str | None = None,
):
    """Generates an ingress for the stack from template

    Args:
        stack_name (str | None, optional): Name of the stack. Defaults to None.
        ingress_type (Literal[frontend, api] | None, optional): The types of ingress that can be created. Defaults to None.
        port (str | None, optional): Port to bind the ingress to. Defaults to None.
        namespace (str | None, optional): Namespace to work in. Defaults to web when building. Defaults to None.
    """
    print("Creating a new Ingress")

    if subfolder == "" or subfolder is None:
        subfolder = input('''      
NOTE: Only put files in BETA subfolder if the image is compiled from the BETA BRANCH of a repository. 
      If a beta websites are in a repo that is still in the MAIN BRANCH, put the files in the MAIN subfolder.
Create in main or beta subfolder (main/beta)? ''')

    if stack_name == "" or stack_name is None:
        stack_name = get_stack_name()
        if subfolder == "beta":
            stack_name = stack_name + "-beta"

    if port == "" or port is None:
        port = get_string_from_input("Enter the port for the ingress (ex. 80): ")

    if namespace == "" or namespace is None:
        namespace = get_namespace("web")

    if ingress_type == "" or ingress_type is None:
        ingress_type = get_valid_ingress_type()

    host = get_string_from_input(
        f"Enter the host for the {ingress_type} ingress (ex. lytle{ '-api' if ingress_type == 'api' else ''}.byu.edu): "
    )

    makedir(f"{subfolder}/{stack_name.split('-api')[0].split('-beta')[0]}")

    # Read in the ingress template

    template = open("templates/ingress-template.yml", "r")
    template = template.read()
    template = template.replace("<NAME>", stack_name)
    template = template.replace("<HOST>", host)
    template = template.replace("<PORT>", port)
    template = template.replace("<NAMESPACE>", namespace)

    # Write the template to a new file
    new_file = open(f"{subfolder}/{stack_name.split('-api')[0].split('-beta')[0]}/{stack_name}-ingress.yml", "w")
    new_file.write(template)
    new_file.close()


def main():
    print("LSIT YML GENERATOR")
    print("Now with TypeSafety™")
    print("Now with AutoPosting 🖥️")

    while True:
        print("Select an option:")
        print("1: Create a new Stack")
        print("2: Create a new Frontend")
        print("3: Create a new Backend")
        print("4: Create a new Ingress")
        print("5: Exit")

        option = get_string_from_input("\nEnter your option: ")

        if option == "1":
            build_stack()

        elif option == "2":
            build_frontend()

        elif option == "3":
            backend()

        elif option == "4":
            ingress()

        elif option == "5":
            print("Exiting")
            break
            
if __name__ == "__main__":
    main()