"""
Migration script to import joined channels from text file to database.
Run this script once after setting up the SQLite database.
"""

from app import app, db, JoinedChannel, init_db

def migrate_joined_channels_to_db():
    """
    Migrate channels from joined_channels.txt to the database.
    """
    try:
        # Read channels from the file
        channels = []
        try:
            with open('joined_channels.txt', 'r', encoding='utf-8') as file:
                channels = [line.strip() for line in file if line.strip()]
            print(f"Read {len(channels)} channels from joined_channels.txt")
        except FileNotFoundError:
            print("joined_channels.txt file not found, nothing to migrate")
            return
        except Exception as e:
            print(f"Error reading joined_channels.txt: {e}")
            return

        # Import channels to the database
        with app.app_context():
            # First, get existing channels in DB to avoid duplicates
            existing_channels = JoinedChannel.query.all()
            existing_urls = {channel.url for channel in existing_channels}
            
            # Add channels that aren't already in the database
            added_count = 0
            for url in channels:
                if url not in existing_urls:
                    new_channel = JoinedChannel(url=url)
                    db.session.add(new_channel)
                    added_count += 1
            
            # Commit changes
            db.session.commit()
            print(f"Successfully migrated {added_count} channels to the database")
    
    except Exception as e:
        print(f"Error during migration: {e}")
        with app.app_context():
            db.session.rollback()

if __name__ == "__main__":
    init_db()  
    migrate_joined_channels_to_db()
    print("Migration complete")