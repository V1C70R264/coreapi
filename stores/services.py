from .models import Store


def ensure_store_for(user):
    """
    Returns the user's store, creating a default one if they don't have
    one yet. Safe to call repeatedly.
    """
    existing = Store.objects.filter(owner=user).first()
    if existing:
        return existing

    # Username-based default so no real name becomes public by accident.
    name = f"{user.username}'s Store"
    if Store.objects.filter(name=name).exists():
        name = f"{name} {user.pk}"

    return Store.objects.create(owner=user, name=name)