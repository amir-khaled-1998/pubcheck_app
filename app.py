# -*- coding: utf-8 -*-
"""
Created on Sun Mar  2 15:44:44 2025

@author: amine
"""

# app.py
from flask import Flask, render_template, jsonify, request, session
import os
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.api import FacebookAdsApi
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Pour la gestion des sessions

# Configuration
class Config:
    FACEBOOK_APP_ID = "VOTRE_APP_ID"
    FACEBOOK_APP_SECRET = "VOTRE_APP_SECRET"

app.config.from_object(Config)

def verifier_lien(url: str, phrases_rupture: list = None) -> dict:
    if phrases_rupture is None:
        phrases_rupture = [
            "rupture de stock",
            "en rupture",
            "stock épuisé",
            "out of stock",
            "sold out",
            "currently unavailable",
            "plus disponible"
        ]
    
    resultat = {
        'status_code': None,
        'est_404': False,
        'rupture_stock': False,
        'message_erreur': None,
        'url': url
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resultat['status_code'] = response.status_code
        resultat['est_404'] = response.status_code == 404
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for error_container in soup.find_all(['div', 'p', 'span'], 
                class_=lambda x: x and ('error' in x.lower() or 'alert' in x.lower())):
                if error_container.text.strip():
                    resultat['message_erreur'] = error_container.text.strip()
                    break
            
            page_text = soup.get_text().lower()
            for phrase in phrases_rupture:
                if phrase.lower() in page_text:
                    resultat['rupture_stock'] = True
                    break
                    
    except Exception as e:
        resultat['message_erreur'] = str(e)
        
    return resultat

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/initialize', methods=['POST'])
def initialize_api():
    data = request.json
    try:
        access_token = data.get('access_token')
        compte_id = data.get('compte_id')
        
        # Stockage temporaire dans la session
        session['access_token'] = access_token
        session['compte_id'] = compte_id
        
        # Test de connexion
        FacebookAdsApi.init(
            app_id=app.config['FACEBOOK_APP_ID'],
            app_secret=app.config['FACEBOOK_APP_SECRET'],
            access_token=access_token
        )
        
        compte = AdAccount(compte_id)
        compte.api_get()  # Test simple pour vérifier l'accès
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/scan', methods=['POST'])
def scan_ads():
    try:
        access_token = session.get('access_token')
        compte_id = session.get('compte_id')
        
        if not access_token or not compte_id:
            return jsonify({'success': False, 'error': 'Session expirée'})
            
        FacebookAdsApi.init(
            app_id=app.config['FACEBOOK_APP_ID'],
            app_secret=app.config['FACEBOOK_APP_SECRET'],
            access_token=access_token
        )
        
        compte = AdAccount(compte_id)
        ads = compte.get_ads(
            fields=[
                'id',
                'name',
                'status',
                'creative',
                'effective_status',
                'preview_shareable_link',
                'tracking_specs'
            ],
            params={'effective_status': ['ACTIVE']}
        )
        
        resultats = []
        for ad in ads:
            lien_produit = None
            if 'creative' in ad and 'link_url' in ad['creative']:
                lien_produit = ad['creative']['link_url']
            elif 'tracking_specs' in ad:
                for spec in ad['tracking_specs']:
                    if 'url' in spec:
                        lien_produit = spec['url']
                        break
                        
            if lien_produit:
                verification = verifier_lien(lien_produit)
                resultats.append({
                    'id_publicite': ad['id'],
                    'nom': ad['name'],
                    'statut': ad['effective_status'],
                    'lien_produit': lien_produit,
                    'lien_apercu': ad.get('preview_shareable_link'),
                    'verification': verification
                })
        
        # Sauvegarde des résultats
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        with open(f'resultats_{timestamp}.json', 'w') as f:
            json.dump(resultats, f, ensure_ascii=False, indent=2)
            
        return jsonify({
            'success': True,
            'resultats': resultats,
            'total': len(resultats)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)