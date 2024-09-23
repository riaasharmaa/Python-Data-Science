# project: MP3
# submitter: Ria Sharma
# partner: none
# hours: ????
import os
import pandas as pd
from collections import deque
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
import time
import requests

class GraphSearcher:
    def __init__(self):
        self.visited = set()
        self.order = []

    #override 
    def visit_and_get_children(self, node):
        raise Exception("must be overridden in sub classes -- don't change me here!")

    #depth-first search
    def dfs_search(self, node):
        self.visited = set()
        self.order = []
        self.dfs_visit(node)

    #helper method for DFS
    def dfs_visit(self, node):
        # If the node has been visited, return immediately to avoid cycles.
        if (node in self.visited): return
        self.visited.add(node)
        children = self.visit_and_get_children(node)
       
        for child in children:
            self.dfs_visit(child)
           
    #breadth-first search
    def bfs_search(self, node):
        self.visited = set()
        self.order = []
        queue = deque([node])
        while queue:
            node = queue.popleft()
            if (node not in self.visited):
                self.visited.add(node)
                children = self.visit_and_get_children(node)
                for child in children:
                    queue.append(child)

class MatrixSearcher(GraphSearcher):
    def __init__(self, df):
        super().__init__()
        self.df = df

    #overrides
    def visit_and_get_children(self, node):
        self.order.append(node)
        return [child for child, has_edge in self.df.loc[node].items() if has_edge]
   
class FileSearcher(GraphSearcher):
    def __init__(self, base_path='file_nodes'):
        super().__init__()
        self.base_path = base_path
       
    #overrides
    def visit_and_get_children(self, node):
        path = os.path.join(self.base_path, node)
        try:
            with open(path, "r") as file:
                content = file.read().strip().split('\n')
                #line = node
                self.order.append(content[0])
                return content[1].split(',') if len(content) > 1 else []
        #if file doesn't exist
        except FileNotFoundError:
            print(f"File not found: {path}")
            return []

    #visited nodes -> single string.
    def concat_order(self):
        return ''.join(self.order)

class WebSearcher(GraphSearcher):
    def __init__(self, driver):
        super().__init__()
        self.driver = driver
        self.data_frames = []

    #overrides
    def visit_and_get_children(self, node):
        self.driver.get(node)
        self.order.append(node)
        self.data_frames.append(pd.read_html(self.driver.page_source)[0])
        links = self.driver.find_elements(By.TAG_NAME, 'a')
        return [link.get_attribute('href') for link in links]

    def table(self):
        return pd.concat(self.data_frames, ignore_index=True)
   
def reveal_secrets(driver, url, travellog):
    #generate a password from the "clue" column of the travellog DataFrame
    password = ''.join(str(clue) for clue in travellog['clue'])
    #visit url with the driver
    driver.get(url)
    #automate typing the password in the box and clicking "GO"
    password_field = driver.find_element(By.ID, 'password-textbox')
    password_field.send_keys(password)
    go_button = driver.find_element(By.ID, 'submit-button')
    go_button.click()
    #wait until the pages is loaded
    time.sleep(10)
    #click the "View Location" button and wait until the result finishes loading
    view_location_button = driver.find_element(By.ID, 'view-location-button')
    view_location_button.click()
    time.sleep(5)
    #save the image that appears to a file named 'Current_Location.jpg'
    image = driver.find_element(By.TAG_NAME, 'img')
    image_src = image.get_attribute('src')
    response = requests.get(image_src, stream=True)
    if response.status_code == 200:
        with open('Current_Location.jpg', 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
    #return the current location that appears on the page
    location_element = driver.find_element(By.ID, 'location')
    current_location = location_element.text
    return current_location
