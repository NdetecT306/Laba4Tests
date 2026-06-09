// backend/frontend/src/pages/Home.js
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ITEMS_PER_PAGE = 5;

function Home() {
  const navigate = useNavigate();
  const { user, logout, api } = useAuth();
  const [chps, setChps] = useState([]);
  const [houses, setHouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notification, setNotification] = useState(null);
  const [selectedObject, setSelectedObject] = useState(null);
  const [selectedType, setSelectedType] = useState(null);
  const [filterType, setFilterType] = useState('all');
  const [viewMode, setViewMode] = useState('list');
  const [visualMode, setVisualMode] = useState('list');
  const [chpStatus, setChpStatus] = useState({});
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(ITEMS_PER_PAGE);

  const checkChpStatus = useCallback((chpId, currentHouses) => {
    const chpHouses = currentHouses.filter(house => house.chpId === chpId);
    if (chpHouses.length === 0) return 'working';
    const allAtMax = chpHouses.every(house => house.temperature === 95);
    const allAtMin = chpHouses.every(house => house.temperature === 40);
    if (allAtMax || allAtMin) return 'off';
    return 'working';
  }, []);

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [chpsRes, housesRes] = await Promise.all([
        api.get('/chps'),
        api.get('/houses')
      ]);
      
      const chpsData = chpsRes.data.map(chp => ({
        id: chp.ID,
        name: chp.Название,
        capacity: chp.Мощность,
        location: chp.Расположение,
        x: chp.Координата_X,
        y: chp.Координата_Y
      }));
      
      const housesData = housesRes.data.map(house => ({
        id: house.ID,
        name: house.Название,
        type: house.Тип,
        chpId: house.ID_ТЭЦ,
        temperature: house.Температура,
        x: house.Координата_X,
        y: house.Координата_Y
      }));
      
      setChps(chpsData);
      setHouses(housesData);
      
      const statuses = {};
      chpsData.forEach(chp => {
        statuses[chp.id] = checkChpStatus(chp.id, housesData);
      });
      setChpStatus(statuses);
      setError(null);
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Сессия истекла. Перенаправление на страницу входа...');
      } else {
        setError('Ошибка загрузки данных. Убедитесь, что сервер запущен.');
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [api, checkChpStatus]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getFilteredItems = () => {
    const allItems = [
      ...chps.map(chp => ({ ...chp, type: 'chp' })),
      ...houses.map(house => ({ ...house, type: 'house' }))
    ];
    
    if (filterType === 'chp') {
      return chps.map(chp => ({ ...chp, type: 'chp' }));
    }
    if (filterType === 'house') {
      return houses.map(house => ({ ...house, type: 'house' }));
    }
    return allItems;
  };

  const filteredItems = getFilteredItems();
  const totalPages = Math.ceil(filteredItems.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedItems = filteredItems.slice(startIndex, startIndex + itemsPerPage);

  useEffect(() => {
    setCurrentPage(1);
  }, [filterType]);

  const deleteChp = async (id, e) => {
    e.stopPropagation();
    
    // Подтверждение удаления ТЭЦ
    const chpToDelete = chps.find(c => c.id === id);
    const chpHouses = houses.filter(house => house.chpId === id);
    const confirmMessage = chpHouses.length > 0
      ? `Вы уверены, что хотите удалить ТЭЦ "${chpToDelete?.name}"?\n\nВНИМАНИЕ: Все ${chpHouses.length} домов, подключённых к этой ТЭЦ, также будут удалены!\nЭто действие нельзя отменить.`
      : `Вы уверены, что хотите удалить ТЭЦ "${chpToDelete?.name}"?\n\nЭто действие нельзя отменить.`;
    
    if (!window.confirm(confirmMessage)) {
      return;
    }
    
    try {
      await api.delete(`/chps/${id}`);
      await loadData();
      if (selectedObject?.id === id && selectedType === 'chp') {
        setViewMode('list');
        setSelectedObject(null);
        setSelectedType(null);
      }
      showNotification(`ТЭЦ "${chpToDelete?.name}" успешно удалена`);
    } catch (err) {
      showNotification('Ошибка при удалении ТЭЦ', 'error');
    }
  };

  const deleteHouse = async (id, e) => {
    e.stopPropagation();
    
    // Подтверждение удаления дома
    const houseToDelete = houses.find(h => h.id === id);
    if (!window.confirm(`Вы уверены, что хотите удалить дом "${houseToDelete?.name}"?\n\nЭто действие нельзя отменить.`)) {
      return;
    }
    
    try {
      await api.delete(`/houses/${id}`);
      await loadData();
      if (selectedObject?.id === id && selectedType === 'house') {
        setViewMode('list');
        setSelectedObject(null);
        setSelectedType(null);
      }
      showNotification(`Дом "${houseToDelete?.name}" успешно удалён`);
    } catch (err) {
      showNotification('Ошибка при удалении дома', 'error');
    }
  };

  const updateTemperature = async (newTemp) => {
    if (selectedType !== 'house' || !selectedObject) return;
    
    let finalTemp = newTemp;
    if (finalTemp < 40) finalTemp = 40;
    if (finalTemp > 95) finalTemp = 95;
    
    const updatedHouse = { ...selectedObject, temperature: finalTemp };
    setSelectedObject(updatedHouse);
    
    const updatedHouses = houses.map(h => 
      h.id === selectedObject.id ? updatedHouse : h
    );
    setHouses(updatedHouses);
    
    const statuses = {};
    chps.forEach(chp => {
      statuses[chp.id] = checkChpStatus(chp.id, updatedHouses);
    });
    setChpStatus(statuses);
    
    try {
      await api.put(`/houses/${selectedObject.id}`, {
        Температура: finalTemp
      });
      
      const message = finalTemp !== newTemp 
        ? `Температура ограничена ${finalTemp}°C (допустимый диапазон 40-95°C)`
        : `Температура изменена на ${finalTemp}°C`;
      showNotification(message, finalTemp === 40 || finalTemp === 95 ? 'warning' : 'success');
      
    } catch (err) {
      showNotification('Ошибка при изменении температуры', 'error');
      console.error(err);
    }
  };

  const handleObjectClick = (obj, type) => {
    setSelectedObject(obj);
    setSelectedType(type);
    setViewMode('detail');
  };

  const handleBackToList = () => {
    setViewMode('list');
    setSelectedObject(null);
    setSelectedType(null);
  };

  const toggleVisualMode = () => {
    setVisualMode(visualMode === 'list' ? 'schema' : 'list');
  };

  const getTemperatureStatus = (temp) => {
    if (temp < 60) return 'cold';
    if (temp <= 80) return 'normal';
    return 'hot';
  };

  const getTemperatureColor = (temp) => {
    const status = getTemperatureStatus(temp);
    switch(status) {
      case 'cold': return '#4299e1';
      case 'normal': return '#ed8936';
      case 'hot': return '#e53e3e';
      default: return '#718096';
    }
  };

  const getPipeColor = (temp, isChpOff = false) => {
    if (isChpOff) return '#000000';
    return getTemperatureColor(temp);
  };

  const Pagination = () => {
    if (totalPages <= 1) return null;
    
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        gap: '0.5rem', 
        padding: '1rem',
        background: 'white',
        borderTop: '1px solid #e2e8f0',
        marginTop: 'auto'
      }}>
        <button
          className="btn btn-secondary small"
          onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
          disabled={currentPage === 1}
          style={{ opacity: currentPage === 1 ? 0.5 : 1 }}
        >
          ← Назад
        </button>
        <span style={{ fontSize: '0.9rem', color: '#4a5568' }}>
          Страница {currentPage} из {totalPages}
        </span>
        <button
          className="btn btn-secondary small"
          onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
          disabled={currentPage === totalPages}
          style={{ opacity: currentPage === totalPages ? 0.5 : 1 }}
        >
          Вперед →
        </button>
      </div>
    );
  };

  if (loading) return <div className="loading">Загрузка...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="home-container">
      {notification && (
        <div className={`notification notification-${notification.type}`}>
          {notification.message}
        </div>
      )}
      <div className="left-panel">
        {viewMode === 'list' ? (
          <>
            <div className="panel-header">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h1>Управление инфраструктурой</h1>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.9rem', opacity: 0.9 }}>{user?.username}</span>
                  <button className="btn btn-secondary small" onClick={logout}>Выйти</button>
                </div>
              </div>
              <button className="btn btn-success add-btn" onClick={() => navigate('/add')}>+ Добавить объект</button>
            </div>
            <div className="filter-buttons">
              <button className={`filter-btn ${filterType === 'all' ? 'active' : ''}`} onClick={() => setFilterType('all')}>Все объекты</button>
              <button className={`filter-btn ${filterType === 'chp' ? 'active' : ''}`} onClick={() => setFilterType('chp')}>ТЭЦ</button>
              <button className={`filter-btn ${filterType === 'house' ? 'active' : ''}`} onClick={() => setFilterType('house')}>Дома</button>
            </div>

            <div className="objects-list">
              {paginatedItems.length === 0 && (
                <div className="empty-state">Нет объектов для отображения</div>
              )}
              
              {paginatedItems.map(item => {
                if (item.type === 'chp') {
                  const isOff = chpStatus[item.id] === 'off';
                  return (
                    <div key={`chp-${item.id}`} className="list-item" onClick={() => handleObjectClick(item, 'chp')} style={{ borderLeft: isOff ? '4px solid #f56565' : 'none' }}>
                      <div className="list-item-header">
                        <div className="list-item-title">
                          <img src="/TEC.jpeg" alt="ТЭЦ" className="list-icon" />
                          {item.name}
                          {isOff && <span style={{ color: '#f56565', marginLeft: '8px' }}>ОТКЛЮЧЕНА</span>}
                        </div>
                        <div>
                          <button className="btn btn-primary small" style={{ marginRight: '5px' }} onClick={(e) => { e.stopPropagation(); navigate(`/edit/${item.id}`); }}>Ред</button>
                          <button className="btn btn-danger small" onClick={(e) => deleteChp(item.id, e)}>Уд</button>
                        </div>
                      </div>
                      <div className="list-item-info">
                        <span>{item.capacity} МВт</span>
                        <span>{item.location}</span>
                        <span>{houses.filter(h => h.chpId === item.id).length} домов</span>
                      </div>
                    </div>
                  );
                } else {
                  const chp = chps.find(c => c.id === item.chpId);
                  const isChpOff = chp && chpStatus[chp.id] === 'off';
                  return (
                    <div key={`house-${item.id}`} className="list-item" onClick={() => handleObjectClick(item, 'house')}>
                      <div className="list-item-header">
                        <div className="list-item-title">
                          <img src={item.type === 'apartment' ? '/Hruchevka.jpg' : '/House.jpeg'} alt="Дом" className="list-icon" />
                          {item.name}
                          {isChpOff && <span style={{ color: '#f56565', marginLeft: '8px' }}>ТЭЦ отключена</span>}
                        </div>
                        <div>
                          <button className="btn btn-primary small" style={{ marginRight: '5px' }} onClick={(e) => { e.stopPropagation(); navigate(`/edit/${item.id}`); }}>Ред</button>
                          <button className="btn btn-danger small" onClick={(e) => deleteHouse(item.id, e)}>Уд</button>
                        </div>
                      </div>
                      <div className="list-item-info">
                        <span>{item.type === 'apartment' ? 'Многоквартирный' : 'Частный'}</span>
                        <span>{chp?.name || 'Не указана'}</span>
                        <span style={{ color: getTemperatureColor(item.temperature), fontWeight: 'bold' }}>{item.temperature}°C</span>
                      </div>
                    </div>
                  );
                }
              })}
            </div>
            
            <Pagination />
          </>
        ) : selectedObject && (
          <div className="detail-panel">
            <div className="detail-header">
              <button className="btn btn-secondary back-btn" onClick={handleBackToList}>← Назад</button>
              <div>
                <button className="btn btn-primary" style={{ marginRight: '10px' }} onClick={() => navigate(`/edit/${selectedObject.id}`)}>Редактировать</button>
                <button className="btn btn-danger" onClick={() => selectedType === 'chp' ? deleteChp(selectedObject.id, { stopPropagation: () => {} }) : deleteHouse(selectedObject.id, { stopPropagation: () => {} })}>Удалить</button>
              </div>
            </div>
            <div className="detail-content">
              {selectedType === 'chp' ? (
                <>
                  <div className="detail-icon">
                    <img src="/TEC.jpeg" alt="ТЭЦ" className="detail-object-image" />
                  </div>
                  <h2 className="detail-name">
                    {selectedObject.name}
                    {chpStatus[selectedObject.id] === 'off' && <span style={{ color: '#f56565', fontSize: '1rem', marginLeft: '10px' }}>(ОТКЛЮЧЕНА)</span>}
                  </h2>
                  <div className="detail-stats">
                    <div className="stat-card">
                      <div className="stat-value">{selectedObject.capacity}</div>
                      <div className="stat-label">МВт мощность</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{houses.filter(h => h.chpId === selectedObject.id).length}</div>
                      <div className="stat-label">подключено домов</div>
                    </div>
                  </div>
                  <div className="detail-info-section">
                    <div className="info-row">
                      <span className="info-label">Расположение:</span>
                      <span className="info-value">{selectedObject.location}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">Статус:</span>
                      <span className="info-value" style={{ color: chpStatus[selectedObject.id] === 'off' ? '#f56565' : '#48bb78', fontWeight: 'bold' }}>
                        {chpStatus[selectedObject.id] === 'off' ? 'ОТКЛЮЧЕНА' : 'РАБОТАЕТ'}
                      </span>
                    </div>
                  </div>
                  <div className="detail-houses">
                    <h3>Подключённые дома</h3>
                    <div className="houses-list">
                      {houses.filter(h => h.chpId === selectedObject.id).map(house => (
                        <div key={house.id} className="house-item" onClick={() => handleObjectClick(house, 'house')}>
                          <div className="house-icon">
                            <img src={house.type === 'apartment' ? '/Hruchevka.jpg' : '/House.jpeg'} alt="Дом" className="house-mini-image" />
                          </div>
                          <div className="house-info">
                            <div className="house-name">{house.name}</div>
                            <div className="house-temp">{house.temperature}°C</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="detail-icon">
                    <img src={selectedObject.type === 'apartment' ? '/Hruchevka.jpg' : '/House.jpeg'} alt="Дом" className="detail-object-image" />
                  </div>
                  <h2 className="detail-name">{selectedObject.name}</h2>
                  <div className="detail-stats">
                    <div className="stat-card">
                      <div className="stat-value">{selectedObject.temperature}°</div>
                      <div className="stat-label">текущая температура</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value">{selectedObject.type === 'apartment' ? 'МКД' : 'Частный'}</div>
                      <div className="stat-label">тип дома</div>
                    </div>
                  </div>
                  <div className="temperature-control">
                    <div className="temperature-display">
                      <div className="temp-label">Температура воды</div>
                      <div className="temp-value" style={{ color: getTemperatureColor(selectedObject.temperature) }}>{selectedObject.temperature}°C</div>
                    </div>
                    <div className="temperature-bar-container">
                      <div className="temperature-bar">
                        <div className="temperature-fill" style={{ width: `${((selectedObject.temperature - 40) / 55) * 100}%`, background: getPipeColor(selectedObject.temperature) }} />
                      </div>
                    </div>
                    <div className="temperature-buttons">
                      <button className="temp-btn" onClick={() => updateTemperature(selectedObject.temperature - 5)}>-5°</button>
                      <button className="temp-btn" onClick={() => updateTemperature(selectedObject.temperature - 1)}>-1°</button>
                      <button className="temp-btn temp-reset" onClick={() => updateTemperature(60)}>60° (норма)</button>
                      <button className="temp-btn" onClick={() => updateTemperature(selectedObject.temperature + 1)}>+1°</button>
                      <button className="temp-btn" onClick={() => updateTemperature(selectedObject.temperature + 5)}>+5°</button>
                    </div>
                  </div>
                  <div className="detail-info-section">
                    <div className="info-row">
                      <span className="info-label">ТЭЦ:</span>
                      <span className="info-value">{chps.find(c => c.id === selectedObject.chpId)?.name || 'Не указана'}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">Тип:</span>
                      <span className="info-value">{selectedObject.type === 'apartment' ? 'Многоквартирный дом' : 'Частный дом'}</span>
                    </div>
                  </div>
                  <div className="pipe-visualization">
                    <div className="pipe-label">Состояние трубы</div>
                    <div className="pipe">
                      <div className="pipe-water" style={{ width: `${((selectedObject.temperature - 40) / 55) * 100}%`, background: getPipeColor(selectedObject.temperature) }}>
                        <span style={{ fontSize: '0.7rem', marginRight: '0.5rem' }}>{Math.round(((selectedObject.temperature - 40) / 55) * 100)}%</span>
                      </div>
                    </div>
                    <div className="pipe-indicator" style={{ color: getPipeColor(selectedObject.temperature), fontWeight: 'bold' }}>
                      {getTemperatureStatus(selectedObject.temperature) === 'cold' ? 'Холодная вода' : 
                       getTemperatureStatus(selectedObject.temperature) === 'normal' ? 'Тёплая вода' : 'Горячая вода'}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="right-panel">
        <div className="schema-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>{visualMode === 'list' ? 'Список объектов' : 'Схема инфраструктуры'}</h2>
          <button className="btn btn-primary small" onClick={toggleVisualMode}>
            {visualMode === 'list' ? 'Переключиться на визуал' : 'Переключиться на список'}
          </button>
        </div>
        <div className="schema-container">
          {visualMode === 'list' ? (
            <div style={{ 
              padding: '1rem', 
              overflowY: 'auto', 
              height: '100%',
              background: '#1a1a2e',
              color: 'white'
            }}>
              <h3 style={{ marginBottom: '1rem', color: '#cbd5e0' }}>Все ТЭЦ</h3>
              {chps.map(chp => (
                <div key={chp.id} style={{ 
                  background: '#16213e', 
                  padding: '0.75rem', 
                  marginBottom: '0.5rem', 
                  borderRadius: '8px',
                  cursor: 'pointer',
                  border: selectedObject?.id === chp.id && selectedType === 'chp' ? '2px solid #ffd700' : 'none'
                }} onClick={() => handleObjectClick(chp, 'chp')}>
                  <div style={{ fontWeight: 'bold' }}>{chp.name}</div>
                  <div style={{ fontSize: '0.8rem', color: '#cbd5e0' }}>{chp.location} | {chp.capacity} МВт</div>
                </div>
              ))}
              <h3 style={{ marginTop: '1.5rem', marginBottom: '1rem', color: '#cbd5e0' }}>Все дома</h3>
              {houses.map(house => {
                const chp = chps.find(c => c.id === house.chpId);
                return (
                  <div key={house.id} style={{ 
                    background: '#16213e', 
                    padding: '0.75rem', 
                    marginBottom: '0.5rem', 
                    borderRadius: '8px',
                    cursor: 'pointer',
                    border: selectedObject?.id === house.id && selectedType === 'house' ? '2px solid #ffd700' : 'none'
                  }} onClick={() => handleObjectClick(house, 'house')}>
                    <div style={{ fontWeight: 'bold' }}>{house.name}</div>
                    <div style={{ fontSize: '0.8rem', color: '#cbd5e0' }}>
                      {house.type === 'apartment' ? 'Многоквартирный' : 'Частный'} | 
                      ТЭЦ: {chp?.name || 'Не указана'} | 
                      {house.temperature}°C
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <svg className="schema-canvas" viewBox="0 0 900 700">
              {houses.map(house => {
                const chp = chps.find(c => c.id === house.chpId);
                if (chp && house.x && house.y) {
                  return (
                    <line
                      key={`connection-${house.id}`}
                      x1={chp.x + 40}
                      y1={chp.y + 40}
                      x2={house.x + 35}
                      y2={house.y + 35}
                      stroke={getPipeColor(house.temperature)}
                      strokeWidth="3"
                      opacity="0.9"
                    />
                  );
                }
                return null;
              })}
              {chps.map(chp => (
                <g key={`chp-svg-${chp.id}`} onClick={() => handleObjectClick(chp, 'chp')} style={{ cursor: 'pointer' }}>
                  <foreignObject x={chp.x} y={chp.y} width="50" height="50">
                    <div style={{ width: '100%', height: '100%', borderRadius: '8px', overflow: 'hidden', border: selectedObject?.id === chp.id && selectedType === 'chp' && viewMode === 'detail' ? '3px solid #ffd700' : '2px solid white' }}>
                      <img src="/TEC.jpeg" alt="ТЭЦ" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                  </foreignObject>
                  <text x={chp.x + 25} y={chp.y + 65} textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">{chp.name}</text>
                </g>
              ))}
              {houses.map(house => {
                const chp = chps.find(c => c.id === house.chpId);
                const isChpOff = chp && chpStatus[chp.id] === 'off';
                return (
                  <g key={`house-svg-${house.id}`} onClick={() => handleObjectClick(house, 'house')} style={{ cursor: 'pointer' }}>
                    <foreignObject x={house.x} y={house.y} width="40" height="40">
                      <div style={{ width: '100%', height: '100%', borderRadius: '6px', overflow: 'hidden', border: selectedObject?.id === house.id && selectedType === 'house' && viewMode === 'detail' ? '3px solid #ffd700' : `2px solid ${getPipeColor(house.temperature, isChpOff)}` }}>
                        <img src={house.type === 'apartment' ? '/Hruchevka.jpg' : '/House.jpeg'} alt="Дом" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      </div>
                    </foreignObject>
                    <text x={house.x + 20} y={house.y + 55} textAnchor="middle" fill={isChpOff ? '#000000' : 'white'} fontSize="9" fontWeight="bold">
                      {isChpOff ? 'OFF' : `${house.temperature}°C`}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>
      </div>
    </div>
  );
}

export default Home;